import streamlit as st
import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Backend API URL
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# Initialize session state
if "token" not in st.session_state:
    st.session_state.token = None
if "current_user" not in st.session_state:
    st.session_state.current_user = None
if "documents" not in st.session_state:
    st.session_state.documents = []
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []


# Helper functions
def login(username: str, password: str) -> bool:
    try:
        response = requests.post(
            f"{BACKEND_URL}/token",
            data={"username": username, "password": password},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        if response.status_code == 200:
            st.session_state.token = response.json().get("access_token")
            st.session_state.current_user = username
            return True
        else:
            st.error("Invalid username or password")
            return False
    except requests.exceptions.RequestException as e:
        st.error(f"Login failed: {str(e)}")
        return False


def register(username: str, email: str, password: str) -> bool:
    try:
        response = requests.post(
            f"{BACKEND_URL}/users/",
            json={
                "username": username,
                "email": email,
                "password": password
            },
            headers={"Content-Type": "application/json"}
        )

        # Debugging: Print raw response
        print("Status Code:", response.status_code)
        print("Response Text:", response.text)

        # First check if response has content
        if not response.text.strip():
            st.error("Empty response from server")
            return False

        try:
            data = response.json()
        except ValueError:
            st.error(f"Invalid server response: {response.text}")
            return False

        if response.status_code == 200:
            st.success("Registration successful! Please log in.")
            return True
        else:
            error_msg = data.get("detail", "Registration failed")
            st.error(error_msg)
            return False

    except requests.exceptions.RequestException as e:
        st.error(f"Connection error: {str(e)}")
        return False
    except Exception as e:
        st.error(f"Unexpected error: {str(e)}")
        return False


def upload_document(file, semester: int, subject: str) -> bool:
    try:
        files = {"file": (file.name, file.getvalue(), file.type)}
        data = {"semester": semester, "subject": subject}

        response = requests.post(
            f"{BACKEND_URL}/documents/upload/",
            files=files,
            data=data,
            headers={"Authorization": f"Bearer {st.session_state.token}"}
        )

        if response.status_code == 200:
            st.success("Document uploaded successfully!")
            return True
        else:
            st.error(f"Upload failed: {response.json().get('detail', 'Unknown error')}")
            return False
    except Exception as e:
        st.error(f"Upload failed: {str(e)}")
        return False


def get_user_documents() -> bool:
    try:
        response = requests.get(
            f"{BACKEND_URL}/documents/",
            headers={"Authorization": f"Bearer {st.session_state.token}"}
        )
        if response.status_code == 200:
            st.session_state.documents = response.json()
            return True
        else:
            st.error("Failed to fetch documents")
            return False
    except Exception as e:
        st.error(f"Error fetching documents: {str(e)}")
        return False


def chat_with_documents(question: str, semester: int = None, subject: str = None):
    try:
        response = requests.post(
            f"{BACKEND_URL}/chat/",
            json={
                "question": question,
                "user_id": st.session_state.current_user,
                "semester": semester,
                "subject": subject
            },
            headers={"Authorization": f"Bearer {st.session_state.token}"}
        )
        return response.json() if response.status_code == 200 else None
    except Exception as e:
        st.error(f"Chat failed: {str(e)}")
        return None


# UI Components
def auth_section():
    st.title("StudyPal - Smart Study Assistant")

    tab1, tab2 = st.tabs(["Login", "Register"])

    with tab1:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                if login(username, password):
                    st.rerun()

    with tab2:
        with st.form("register_form"):
            username = st.text_input("Username")
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Register"):
                if register(username, email, password):
                    st.rerun()


def main_app():
    st.sidebar.title(f"Welcome, {st.session_state.current_user}")

    if st.sidebar.button("Logout"):
        st.session_state.token = None
        st.session_state.current_user = None
        st.session_state.documents = []
        st.session_state.chat_history = []
        st.rerun()

    menu_options = ["Chat", "Upload Documents", "View Documents"]
    choice = st.sidebar.radio("Navigation", menu_options)

    if choice == "Chat":
        st.header("Chat with Your Documents")

        # Filter options
        col1, col2 = st.columns(2)
        with col1:
            semester_filter = st.number_input("Filter by Semester", min_value=1, max_value=10, value=None)
        with col2:
            subject_filter = st.text_input("Filter by Subject", "")

        # Chat history
        for message in st.session_state.chat_history:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                if message.get("sources"):
                    with st.expander("Sources"):
                        for source in message["sources"]:
                            st.write(source)

        # Chat input
        if prompt := st.chat_input("Ask a question about your documents..."):
            with st.chat_message("user"):
                st.markdown(prompt)

            st.session_state.chat_history.append({"role": "user", "content": prompt})

            with st.chat_message("assistant"):
                response = chat_with_documents(
                    prompt,
                    semester=semester_filter if semester_filter else None,
                    subject=subject_filter if subject_filter else None
                )

                if response:
                    st.markdown(response["answer"])
                    if response["sources"]:
                        with st.expander("Sources"):
                            for source in response["sources"]:
                                st.write(source)

                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": response["answer"],
                        "sources": response["sources"]
                    })
                else:
                    st.error("Failed to get response from the assistant")

    elif choice == "Upload Documents":
        st.header("Upload Study Materials")

        with st.form("upload_form"):
            semester = st.number_input("Semester", min_value=1, max_value=10, value=1)
            subject = st.text_input("Subject", "Computer Science")
            file = st.file_uploader("Choose a file", type=["pdf", "docx", "txt"])
            if st.form_submit_button("Upload") and file is not None:
                if upload_document(file, semester, subject):
                    get_user_documents()

    elif choice == "View Documents":
        st.header("Your Study Materials")

        if st.button("Refresh Documents"):
            get_user_documents()

        if st.session_state.documents:
            for doc in st.session_state.documents:
                with st.expander(f"{doc['title']} - Semester {doc['semester']}, {doc['subject']}"):
                    st.write(f"Uploaded by: {st.session_state.current_user}")
                    st.write(f"Subject: {doc['subject']}")
                    st.write(f"Semester: {doc['semester']}")
        else:
            st.info("No documents uploaded yet.")


# Main app logic
def main():
    st.set_page_config(page_title="StudyPal", page_icon=":books:", layout="wide")

    if st.session_state.token is None:
        auth_section()
    else:
        main_app()


if __name__ == "__main__":
    main()


# import streamlit as st
# from streamlit_option_menu import option_menu

# st.set_page_config(page_title="StudyPal", layout="wide")

# # --- SIDEBAR NAVIGATION ---
# with st.sidebar:
#     st.markdown("### 📘 StudyPal")
#     selected = option_menu(
#         menu_title=None,
#         options=["Home", "Upload Documents", "My Semesters", "Ask AI", "Settings"],
#         icons=["house", "cloud-upload", "calendar", "robot", "gear"],
#         menu_icon="cast",
#         default_index=0,
#     )

# # --- TOP HEADER ---
# col1, col2 = st.columns([8, 1])
# with col1:
#     st.markdown("### 👋 Welcome back, **Ali**")
# with col2:
#     st.button("Logout", use_container_width=True)

# # --- SEMESTER DOCUMENTS MOCK DATA ---
# semester_docs = {
#     "Semester 1": [
#         "Engineering Mathematics.pdf",
#         "Physics Notes.pdf",
#         "Last Year Questions.docx"
#     ],
#     "Semester 2": [
#         "Digital Logic.pdf",
#         "Python Lab Manual.pdf",
#         "Internal Exam Qs.pdf"
#     ]
# }

# # --- MAIN CONTENT ---
# if selected == "Home":
#     st.markdown("## 🗂️ Your Semesters")
#     cols = st.columns(2)

#     for idx, (semester, docs) in enumerate(semester_docs.items()):
#         with cols[idx % 2]:
#             with st.container():
#                 st.markdown(f"#### 📘 {semester}")
#                 st.button("➕ Add document", key=f"add_{semester}")
#                 for doc in docs:
#                     col1, col2 = st.columns([6, 1])
#                     with col1:
#                         st.markdown(f"📄 {doc}")
#                     with col2:
#                         st.button("Ask AI", key=f"ask_{doc}")

#     # --- DOCUMENT UPLOAD ---
#     st.markdown("---")
#     st.markdown("### 📤 Upload Document")
#     uploaded_file = st.file_uploader("Drag and drop or choose file", type=["pdf", "docx", "txt"])

# elif selected == "Ask AI":
#     st.markdown("## 🤖 Ask AI from Your Documents")
#     col1, col2 = st.columns([2, 6])

#     with col1:
#         model = st.selectbox("Model:", ["OpenAI", "Groq", "Ollama"])

#     with col2:
#         user_question = st.text_area("Ask AI anything from your documents...", height=100,
#                                      placeholder="What is Kirchhoff’s voltage law?")

#     if st.button("Upload"):
#         if user_question.strip():
#             st.success(f"Query sent to {model} model.")
#         else:
#             st.warning("Please enter a question.")

# elif selected == "Upload Documents":
#     st.markdown("## 📤 Upload Your Study Materials")
#     uploaded_files = st.file_uploader("Upload one or more documents", accept_multiple_files=True, type=["pdf", "docx", "txt"])
#     if uploaded_files:
#         for file in uploaded_files:
#             st.success(f"Uploaded: {file.name}")

# elif selected == "My Semesters":
#     st.markdown("## 📚 My Semesters")
#     for semester, docs in semester_docs.items():
#         st.markdown(f"### 📘 {semester}")
#         for doc in docs:
#             st.markdown(f"- 📄 {doc}")

# elif selected == "Settings":
#     st.markdown("## ⚙️ Settings")
#     st.info("Admin controls and backend configuration will appear here.")


