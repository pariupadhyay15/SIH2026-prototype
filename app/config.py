from dotenv import load_dotenv
from langchain_huggingface import (
    ChatHuggingFace,
    HuggingFaceEndpoint,
    HuggingFaceEmbeddings
)

load_dotenv()

EMBEDDING_MODEL_NAME = "AkshitaS/bhasha-embed-v0"
FAISS_INDEX_PATH = "faiss_index"

chat_model = HuggingFaceEndpoint(
    repo_id="meta-llama/Llama-3.1-8B-Instruct",
    task="text-generation",
    temperature=0.2
)

llm = ChatHuggingFace(llm=chat_model)

embeddings_model = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)