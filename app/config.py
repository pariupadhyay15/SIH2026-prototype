import os
from dotenv import load_dotenv
from langchain_huggingface import (
    ChatHuggingFace,
    HuggingFaceEndpoint
)

load_dotenv()


chat_model = HuggingFaceEndpoint(
    repo_id="meta-llama/Llama-3.1-8B-Instruct",
    task="text-generation",
    temperature=0.3,
    max_new_tokens=1024
)

llm = ChatHuggingFace(llm=chat_model)