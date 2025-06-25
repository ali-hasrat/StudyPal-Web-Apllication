import os
from typing import List
from pypdf import PdfReader
from docx import Document as DocxDocument
import unstructured.partition.auto


def extract_text_from_file(file_path: str) -> str:
    if file_path.endswith('.pdf'):
        reader = PdfReader(file_path)
        text = "\n".join([page.extract_text() for page in reader.pages])
    elif file_path.endswith('.docx'):
        doc = DocxDocument(file_path)
        text = "\n".join([para.text for para in doc.paragraphs])
    elif file_path.endswith('.txt'):
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
    else:
        # Use unstructured as fallback
        elements = unstructured.partition.auto.partition(filename=file_path)
        text = "\n".join([str(el) for el in elements])

    return text


def split_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> List[str]:
    words = text.split()
    chunks = []
    current_chunk = []
    current_length = 0

    for word in words:
        if current_length + len(word) + 1 <= chunk_size:
            current_chunk.append(word)
            current_length += len(word) + 1
        else:
            chunks.append(" ".join(current_chunk))
            current_chunk = current_chunk[-chunk_overlap:] + [word]
            current_length = sum(len(w) + 1 for w in current_chunk)

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks