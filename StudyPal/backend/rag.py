import os
from typing import List, Optional
import chromadb
from chromadb.utils import embedding_functions
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma

from langchain.schema import Document as LangchainDocument
from .config import settings
from .utils import extract_text_from_file, split_text


class RAGSystem:
    def __init__(self):
        self.embedding_function = OpenAIEmbeddings(
            model=settings.embedding_model,
            openai_api_key=settings.openai_api_key
        )

        self.client = chromadb.PersistentClient(path=settings.chroma_db_path)
        self.vector_store = Chroma(
            client=self.client,
            collection_name="studypal_documents",
            embedding_function=self.embedding_function
        )

        self.llm = ChatOpenAI(
            model_name=settings.model_name,
            temperature=0.7,
            openai_api_key=settings.openai_api_key
        )

        self.prompt_template = """Use the following pieces of context to answer the question at the end. 
        If you don't know the answer, just say that you don't know, don't try to make up an answer.
        Always provide the source document(s) you used to answer the question.

        {context}

        Question: {question}
        Answer:"""

        self.qa_prompt = PromptTemplate(
            template=self.prompt_template,
            input_variables=["context", "question"]
        )

    def ingest_document(self, file_path: str, metadata: dict) -> bool:
        try:
            text = extract_text_from_file(file_path)
            chunks = split_text(text)

            documents = []
            metadatas = []
            ids = []

            for i, chunk in enumerate(chunks):
                doc_id = f"{metadata['user_id']}_{metadata['semester']}_{metadata['subject']}_{os.path.basename(file_path)}_{i}"
                documents.append(chunk)
                metadatas.append(metadata)
                ids.append(doc_id)

            self.vector_store.add_texts(
                texts=documents,
                metadatas=metadatas,
                ids=ids
            )
            return True
        except Exception as e:
            print(f"Error ingesting document: {e}")
            return False

    def query(self, question: str, user_id: int, semester: Optional[int] = None, subject: Optional[str] = None) -> dict:
        try:
            filter = {"user_id": user_id}
            if semester:
                filter["semester"] = semester
            if subject:
                filter["subject"] = subject

            qa_chain = RetrievalQA.from_chain_type(
                llm=self.llm,
                chain_type="stuff",
                retriever=self.vector_store.as_retriever(
                    search_kwargs={"filter": filter, "k": 4}
                ),
                chain_type_kwargs={"prompt": self.qa_prompt},
                return_source_documents=True
            )

            result = qa_chain({"query": question})

            sources = list(set([doc.metadata["title"] for doc in result["source_documents"]]))

            return {
                "answer": result["result"],
                "sources": sources
            }
        except Exception as e:
            print(f"Error querying RAG system: {e}")
            return {
                "answer": "Sorry, I encountered an error processing your request.",
                "sources": []
            }

    def get_user_documents(self, user_id: int) -> List[dict]:
        try:
            collection = self.client.get_collection("studypal_documents")
            results = collection.get(
                where={"user_id": user_id},
                include=["metadatas"]
            )

            # Get unique documents by title
            unique_docs = {}
            for metadata in results["metadatas"]:
                if metadata["title"] not in unique_docs:
                    unique_docs[metadata["title"]] = {
                        "semester": metadata["semester"],
                        "subject": metadata["subject"],
                        "user_id": metadata["user_id"]
                    }

            return [{"title": title, **info} for title, info in unique_docs.items()]
        except Exception as e:
            print(f"Error getting user documents: {e}")
            return []