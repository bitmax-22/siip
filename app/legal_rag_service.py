# legal_rag_service.py
import os
from typing import List
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.chains import RetrievalQA
from langchain_community.document_loaders import PyPDFLoader
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain.vectorstores import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
from flask import current_app

class LegalRAGService:
    def __init__(self, config):
        self.google_api_key = config['GOOGLE_API_KEY']
        self.chroma_db_path = config.get('CHROMA_DB_PATH', './chroma_db') # Usa el valor de la configuración o el valor por defecto
        self.llm = ChatGoogleGenerativeAI(
            model="models/gemini-2.5-pro",
            google_api_key=self.google_api_key,
            temperature =0.3, # Ajusta la creatividad
            convert_system_message_to_human=True # Para compatibilidad con algunos prompts
        )
        self.embedding = GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=self.google_api_key) # Modelo de embedding
        self.qa = None
        self.load_chroma_db()

    def load_chroma_db(self):
        # Intenta cargar la base de datos existente
        try:
            self.vector_db = Chroma(persist_directory=self.chroma_db_path, embedding_function=self.embedding)
            print(f"Chroma DB cargada desde: {self.chroma_db_path}")
        except Exception as e:
            print(f"Error al cargar la base de datos Chroma: {e}")
            self.vector_db = None

        # Si no existe, crea una nueva (o rellena con documentos)
        if self.vector_db is None:
            print("Creando una nueva base de datos Chroma...")
            self.vector_db = self.create_and_populate_chroma_db()

        # Configura RetrievalQA (si la base de datos se cargó o creó correctamente)
        if self.vector_db:
            self.qa = RetrievalQA.from_chain_type(
                llm=self.llm,
                chain_type="stuff", # Considera otras opciones como "map_reduce" o "refine" si es necesario
                retriever=self.vector_db.as_retriever(),
                return_source_documents=True,
            )
            print("RetrievalQA configurado.")
        else:
            print("No se pudo configurar RetrievalQA. La base de datos Chroma no se cargó o creó correctamente.")

    def create_and_populate_chroma_db(self):
        # Asegúrate de que la carpeta exista
        if not os.path.exists(self.chroma_db_path):
            os.makedirs(self.chroma_db_path)

        # Carga los documentos (PDFs de ejemplo)
        pdf_path = os.path.join(current_app.root_path, 'data', 'ejemplo.pdf') # Ruta relativa al directorio de la app
        if not os.path.exists(pdf_path):
            print(f"El archivo PDF no se encontró en la ruta especificada: {pdf_path}")
            return None  # O maneja el error de otra manera

        try:
            loader = PyPDFLoader(pdf_path)
            documents = loader.load()
        except Exception as e:
            print(f"Error al cargar el archivo PDF: {e}")
            return None # Maneja el error de otra manera

        # Divide el texto en fragmentos
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        texts = text_splitter.split_documents(documents)

        # Crea la base de datos Chroma
        try:
            vector_db = Chroma.from_documents(texts, self.embedding, persist_directory=self.chroma_db_path)
            vector_db.persist()
            print(f"Base de datos Chroma creada y guardada en: {self.chroma_db_path}")
            return vector_db
        except Exception as e:
            print(f"Error al crear la base de datos Chroma: {e}")
            return None # Maneja el error de otra manera

    def get_answer(self, query: str):
        if self.qa is None:
            return "Lo siento, no puedo responder tu pregunta en este momento. La base de datos no está disponible."
        try:
            result = self.qa({"query": query})
            return result
        except Exception as e:
            print(f"Error al obtener la respuesta: {e}")
            return "Hubo un error al procesar tu solicitud."

    def get_relevant_chunks(self, query: str, top_k: int = 3):
        if self.vector_db is None:
            return []
        try:
            results = self.vector_db.similarity_search(query, k=top_k)
            return results
        except Exception as e:
            print(f"Error al buscar chunks relevantes: {e}")
            return []
