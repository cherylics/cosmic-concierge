# utils/config.py
import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

MODEL = "gemini-1.5-flash"     # change in ONE place now
client = genai.Client()        #reads GEMINI_API_KEY from env