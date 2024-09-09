import streamlit as st
import pandas as pd
import snowflake.connector
import os 
from dotenv import load_dotenv

import tempfile

# Load environment variables
load_dotenv()

# Retrieve Snowflake credentials from environment variables
account = st.secrets["SNOWFLAKE_ACCOUNT"]
user = st.secrets["SNOWFLAKE_USER"]
password = st.secrets["SNOWFLAKE_PASSWORD"]
warehouse = st.secrets["SNOWFLAKE_WAREHOUSE"]
database = st.secrets["SNOWFLAKE_DATABASE"]
schema = st.secrets["SNOWFLAKE_SCHEMA"]
# Attempt to connect to Snowflake
try:
    conn = snowflake.connector.connect(
       account= account, 
       user=user,
       password=password,
       warehouse= warehouse, 
       database= database,
       schema=schema
    )
    cursor = conn.cursor()
except Exception as e:
    st.error(f"Error connecting to Snowflake: {e}")
    cursor = None  # Ensure cursor is defined even if connection fails

# Default pandas settings
pd.set_option("max_colwidth", None)

# Default Values
num_chunks = 3
slide_window = 7

def main():
    st.title(":speech_balloon: Chat Document Assistant with Snowflake Cortex")
    
    st.write("### Snowflake Connection Details")
    display_snowflake_details()
    
    st.write("### Upload a Document")
    uploaded_file = st.file_uploader("Choose a file")
    if uploaded_file is not None:
        try:
            upload_to_snowflake(uploaded_file)
            st.success("File uploaded successfully!")
        except Exception as e:
            st.error(f"Error uploading file: {e}")

    st.write("### List of Documents")
    st.write("This is the list of documents you already have and that will be used to answer your questions:")
    if cursor:
        try:
            cursor.execute("LIST @docs")
            docs_available = cursor.fetchall()
            list_docs = [doc[0] for doc in docs_available]
            st.dataframe(list_docs)
        except Exception as e:
            st.error(f"Error fetching documents: {e}")
    else:
        st.error("Cursor is not defined. Unable to fetch documents.")

    config_options()
    init_messages()

    for message in st.session_state.get("messages", []):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if question := st.chat_input("What do you want to know about your products?"):
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            question = question.replace("'", "")
            with st.spinner(f"{st.session_state.model_name} thinking..."):
                response = complete(question)

                # Check if the response is valid before trying to access it
                if response is not None and not response.empty:
                    res_text = response.iloc[0]["RESPONSE"].replace("'", "")
                    message_placeholder.markdown(res_text)
                else:
                    st.error("No response received from Snowflake.")
                    message_placeholder.markdown("No response available.")
        
        st.session_state.messages.append({"role": "assistant", "content": res_text})

def display_snowflake_details():
    if cursor:
        try:
            cursor.execute("SELECT CURRENT_WAREHOUSE(), CURRENT_DATABASE(), CURRENT_SCHEMA()")
            warehouse, database, schema = cursor.fetchone()
            st.write(f"**Warehouse**: {warehouse}")
            st.write(f"**Database**: {database}")
            st.write(f"**Schema**: {schema}")
        except Exception as e:
            st.write("Error fetching Snowflake connection details:", e)
    else:
        st.write("No Snowflake connection available.")


def upload_to_snowflake(uploaded_file, cursor):
    if cursor:
        file_name = uploaded_file.name
        file_content = uploaded_file.read()  # In-memory file content
        
        # Save the file temporarily using tempfile
        try:
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(file_content)
                temp_file_path = temp_file.name

            # Upload the file to Snowflake stage
            put_command = f"PUT 'file://{temp_file_path}'@ARYAN_GUPTA_DB.DATA.DOCS AUTO_COMPRESS=TRUE"
            cursor.execute(put_command)

            # Clean up the temp file after successful upload
            os.remove(temp_file_path)

            st.success(f"File '{file_name}' successfully uploaded to stage @ARYAN_GUPTA_DB.DATA.DOCS.")
        except Exception as e:
            st.error(f"Error uploading file to Snowflake: {e}")
        finally:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
    else:
        st.error("No connection to Snowflake for file upload.")


def config_options():
    st.sidebar.selectbox('Select your model:', (
        'mixtral-8x7b', 'snowflake-arctic', 'mistral-large', 'llama3-8b', 'llama3-70b',
        'reka-flash', 'mistral-7b', 'llama2-70b-chat', 'gemma-7b'), key="model_name")
    st.sidebar.checkbox('Do you want that I remember the chat history?', key="use_chat_history", value=True)
    st.sidebar.checkbox('Debug: Click to see summary generated of previous conversation', key="debug", value=True)
    st.sidebar.button("Start Over", key="clear_conversation")
    st.sidebar.expander("Session State").write(st.session_state)

def init_messages():
    if st.session_state.get("clear_conversation", False) or "messages" not in st.session_state:
        st.session_state.messages = []

def get_similar_chunks(question):
    # SQL query with Python string formatting
    cmd = f"""
        WITH results AS (
            SELECT RELATIVE_PATH, 
            VECTOR_COSINE_SIMILARITY(docs_chunks_table.chunk_vec, 
            SNOWFLAKE.CORTEX.EMBED_TEXT_768('e5-base-v2', '{question}')) AS similarity, 
            chunk
            FROM docs_chunks_table
            ORDER BY similarity DESC
            LIMIT {num_chunks}
        )
        SELECT chunk, relative_path FROM results
    """

    # Execute query using cursor instead of pd.read_sql to avoid the parameter mismatch
    try:
        cursor.execute(cmd)
        df_chunks = pd.DataFrame(cursor.fetchall(), columns=[col[0] for col in cursor.description])
        return "".join(df_chunks['CHUNK'].replace("'", ""))
    except Exception as e:
        st.error(f"Error fetching similar chunks: {e}")
        return ""
    




def get_chat_history():
    """Get chat history from the session state, based on the sliding window."""
    chat_history = []
    start_index = max(0, len(st.session_state.messages) - slide_window)
    for i in range(start_index, len(st.session_state.messages) - 1):
        chat_history.append(st.session_state.messages[i]["content"])
    return chat_history



def summarize_question_with_history(chat_history, question):
    """Summarize the question along with the chat history to get the right context."""
    
    # Escape special characters in the chat history and question to prevent SQL syntax errors
    chat_history_str = " ".join(chat_history).replace("'", "''")  # Escape single quotes
    question = question.replace("'", "''")  # Escape single quotes in the current question

    # Create the summarization prompt
    prompt = f"""
        Based on the chat history below and the question, generate a query that extends the question
        with the chat history provided. The query should be in natural language. 
        Answer with only the query. Do not add any explanation.
        
        <chat_history>
        {chat_history_str}
        </chat_history>
        <question>
        {question}
        </question>
    """

    # Use Python string formatting instead of placeholders in the SQL query
    cmd = f"SELECT snowflake.cortex.complete('{st.session_state.model_name}', '{prompt}') AS response"
    
    try:
        # Execute the query
        cursor.execute(cmd)
        df_response = pd.DataFrame(cursor.fetchall(), columns=[desc[0] for desc in cursor.description])
        
        # Check if there is a valid response
        if df_response is not None and not df_response.empty:
            summary = df_response.iloc[0]["RESPONSE"].replace("'", "")
        else:
            summary = ""
        
        if st.session_state.debug:
            st.sidebar.text("Summary to be used to find similar chunks in the docs:")
            st.sidebar.caption(summary)
        
        return summary
    except Exception as e:
        st.error(f"Error summarizing question with history: {e}")
        return ""


def create_prompt(myquestion):
    if st.session_state.use_chat_history:
        chat_history = get_chat_history()
        if chat_history:
            question_summary = summarize_question_with_history(chat_history, myquestion)
            prompt_context = get_similar_chunks(question_summary)
        else:
            prompt_context = get_similar_chunks(myquestion)
    else:
        prompt_context = get_similar_chunks(myquestion)
        chat_history = ""

    # Show debug information only if enabled
    if st.session_state.get("debug", False):
        st.write(f"Prompt Context: {prompt_context}")
        st.write(f"Chat History: {chat_history}")

    # Ensure that the AI is instructed not to mention the chat history or context
    prompt = f"""
       You are an expert chat assistant that extracts information from the CONTEXT provided
       between <context> and </context> tags.
       You offer a chat experience considering the information included in the CHAT HISTORY
       provided between <chat_history> and </chat_history> tags.
       When answering the question contained between <question> and </question> tags,
       be concise and do not hallucinate. 
       If you don’t have the information just say so.
       
       Do not mention the CONTEXT used in your answer.
       Do not mention the CHAT HISTORY used in your answer.
       
       <chat_history>
       {chat_history}
       </chat_history>
       <context>          
       {prompt_context}
       </context>
       <question>  
       {myquestion}
       </question>
       Answer:
       """
    return prompt



def complete(myquestion):
    st.write(f"Creating prompt for question: {myquestion}")
    try:
        # Generate the prompt from the user's question
        prompt = create_prompt(myquestion)
        prompt = prompt.replace("'", "''")  # Escape single quotes to avoid SQL injection

        # Construct the SQL query with string interpolation
        cmd = f"SELECT snowflake.cortex.complete('{st.session_state.model_name}', '{prompt}') AS response"
        
        # Execute the query and fetch results
        cursor.execute(cmd)
        df_response = cursor.fetchall()

        # Check if the query returned results
        if df_response and len(df_response) > 0:
            return pd.DataFrame(df_response, columns=[desc[0] for desc in cursor.description])
        else:
            st.error("No response received from Snowflake.")
            return None
    except Exception as e:
        st.error(f"Error in completing the request: {e}")
        return None


if __name__ == "__main__":
    main()
