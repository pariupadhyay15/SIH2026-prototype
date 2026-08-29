from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import PromptTemplate
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_huggingface import HuggingFaceEndpointEmbeddings
from langchain_core.runnables import RunnableParallel , RunnablePassthrough , RunnableLambda
from langchain_core.output_parsers import StrOutputParser
from langchain_community.document_loaders import PyPDFLoader




from dotenv import load_dotenv

load_dotenv()
chat = HuggingFaceEndpoint(
    repo_id="meta-llama/Llama-3.1-8B-Instruct",
    task="text-generation",
    temperature=0.2
    
)

llm = ChatHuggingFace(llm=chat)

embeddings_model = HuggingFaceEndpointEmbeddings(
    model="BAAI/bge-m3",
    task="feature-extraction"
)

loader = PyPDFLoader(r"D:\SIH2026\bis.pdf")
docs = loader.load()

splitter = RecursiveCharacterTextSplitter(chunk_size =800 , chunk_overlap=100)
chunks = splitter.split_documents(docs)

vector_store=FAISS.from_documents(chunks , embeddings_model)
retriever = vector_store.as_retriever(search_type = "similarity" , search_kwargs={'k':4})

prompt = PromptTemplate(
    template = """""
    You are a helpful assistant
    answer ONLY from the provided  context
    if the context is insufficient , just say you don't know.

    {context}
    Question {question}
    """,

    input_variables=['context' , 'question']
)

question = "What core activities is the Bureau of Indian Standards (BIS) engaged in as the National Standards Body of India?"

retrieved_docs = retriever.invoke(question)

context_text = "\n\n". join (doc.page_content for doc in retrieved_docs)

final_prompt = prompt.invoke({"context" : context_text, "question" : question})

answer = llm.invoke(final_prompt)
print(answer.content)