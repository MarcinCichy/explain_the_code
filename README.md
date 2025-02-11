# Explain the Code

**Explain the Code** is a web application written in Python that helps explain Python code in a simple and understandable way. The application splits the provided code into logical sections—using a combination of regular expressions and an AI-driven intelligent split—and generates step-by-step explanations for each section via OpenAI's ChatGPT. The solution is designed with beginner programmers in mind, such as teenagers learning to code.

## Features

- **Code Explanation:** Automatically splits code into sections (e.g., function definitions, classes, loops, conditionals) and generates detailed, step-by-step explanations.
- **Intelligent Code Splitting:** Uses the OpenAI model to divide the code into logical sections with brief titles, making programming concepts easier to understand.
- **Web Interface:** A user-friendly interface with three panels:
  - **Left Panel:** Displays a list of conversations.
  - **Middle Panel:** Contains a text area for pasting code.
  - **Right Panel:** Shows the generated explanations.
- **Conversation Management:** Create, load, delete, and reset conversations (data is stored in a JSON file).
- **Syntax Highlighting:** Utilizes the `highlight.js` library for visually appealing code display.

## Requirements

- Python 3.7 or newer (tested on Python 3.11)
- Flask
- python-dotenv
- openai (OpenAI API client)

## Installation

1. **Clone the Repository:**

   ```bash
   git clone https://github.com/your-username/explain-the-code.git
   cd explain-the-code
2. **Create a Virtual Environment:**

    ```bash
    python -m venv venv
    ```

3. **Activate the Virtual Environment:**

    On Windows:
    ```bash
    venv\Scripts\activate
    ```
    On Unix/MacOS:
   
    ```bash
    source venv/bin/activate
    ```
4. Install Required Packages:

    If you have a requirements.txt file (if not, create one with Flask, python-dotenv, openai, etc.):

    ```bash
    pip install -r requirements.txt
    ```
## Configuration
   1. **Create a .env File:**

        In the root directory of the project, create a file named .env and add your OpenAI API key:

       ```bash
        OPENAI_API_KEY=your-api-key
       ```


   2. **Ensure that your API key and environment configuration are correct.**

## Running the Application
Start the application by running:

  ```bash
  python app.py
  ```
Then open your web browser and navigate to http://127.0.0.1:5000.

## How to Use
1. **New Conversation:** Click the "New Conversation" button to start a new session.
2. **Paste Your Code:** Enter your Python code into the text area in the middle panel.
3. **Explain Code:** Click the "Explain" button to initiate the process of splitting and explaining the code.
4. **View Results:** The generated explanations will appear in the right panel. The left panel allows you to browse, delete, or reload previous conversations.
5. **Reset and Exit:** Use the "Reset Conversation" and "Exit" buttons to clear the interface or end your session.

## Troubleshooting
* Error During Intelligent Code Splitting:

    If you encounter an error such as:

```pgsql

Error during intelligent code splitting: Expecting value: line 1 column 1 (char 0)
```
this indicates that the API did not return valid JSON. To resolve this:

- Verify that your API key is correctly set in the .env file.
- Ensure that the prompt in the smart_split_code_snippet function is specific enough to force the model to return pure JSON.
- Check the logs to review the API response (you may temporarily add a print statement for the result variable).
- **Installation Issues:**

    Ensure that all required packages are installed in your activated virtual environment.

## License

 This project is licensed under the MIT License. See the LICENSE file for details.

## Acknowledgements

Inspired by various educational tools designed for teaching programming and explaining code.