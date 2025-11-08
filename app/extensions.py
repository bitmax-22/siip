from flask_sqlalchemy import SQLAlchemy
import google.generativeai as genai

db = SQLAlchemy()
gemini_model = None # Se configurará en create_app