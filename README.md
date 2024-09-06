# Snowflake Chat Document Assistant

This project is a Streamlit application that acts as a chat document assistant using Snowflake as the backend. The application allows users to interact with documents stored in a Snowflake stage and perform various queries on them.

## Setup

### Prerequisites

- Python 3.7 or higher
- pip (Python package installer)
- A Snowflake account with appropriate access

### Installation

 **Clone the Repository**

   Clone the repository to your local machine:


2. pip install -r requirements.txt
3. Create a .env file in the root directory of your project and add your Snowflake credentials and other necessary configurations. Use the .env.example file as a template:

        SNOWFLAKE_ACCOUNT=your_snowflake_account
        SNOWFLAKE_USER=your_snowflake_user
        SNOWFLAKE_PASSWORD=your_snowflake_password
        SNOWFLAKE_WAREHOUSE=your_snowflake_warehouse
        SNOWFLAKE_DATABASE=your_snowflake_database
        SNOWFLAKE_SCHEMA=your_snowflake_schema

4. Run the streamlit application through streamlit run app.py



### Usage
## Main Features

1. View Snowflake Connection Details: Displays the current Snowflake warehouse, database, and schema.
2. List Documents: Lists the documents stored in the specified Snowflake stage.
3. Query Documents: Allows users to ask questions about the documents and get responses.
4. Uploading Files:
    Currently, the feature for uploading files directly through the Streamlit app is not implemented. You can manually upload files to the Snowflake stage using the Snowflake CLI or Python scripts.
5. Querying Documents
    Interact with the chat input to query information about your documents. The assistant will provide concise answers based on the document context.




