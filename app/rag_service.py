import os
from dotenv import load_dotenv
from tavily import TavilyClient
from langchain_core.prompts import PromptTemplate


from app.config import llm

load_dotenv()

tavily_api_key = os.getenv("TAVILY_API_KEY")
if not tavily_api_key:
    raise ValueError("TAVILY_API_KEY is not set in your .env file.")

tavily_client = TavilyClient(api_key=tavily_api_key)



def get_web_results(user_question, max_results=5):
    """
    Constructs targeted queries to retrieve active, official BIS standards,
    QCOs, and amendments.
    """
    search_query = (
        f"Bureau of Indian Standards BIS active latest revision "
        f"amended IS standard QCO {user_question}"
    )

    try:
        response = tavily_client.search(
            query=search_query,
            search_depth="advanced",
            max_results=max_results,
            include_domains=[
                "bis.gov.in",
                "standards.bis.gov.in",
                "manakonline.in",
                "crsbis.in",
                "pib.gov.in",
                "egazette.gov.in"
            ]
        )
    except Exception as e:
        print(f"Tavily search error: {e}")
        return [], search_query

    results = response.get("results", [])
    cleaned_results = []

    for result in results:
        title = result.get("title", "").strip()
        url = result.get("url", "").strip()
        content = result.get("content", "").strip()

        if content:
            cleaned_results.append({
                "title": title,
                "url": url,
                "content": content
            })

    return cleaned_results, search_query



def format_web_context(results):
    if not results:
        return "No relevant information was retrieved from official BIS web sources."

    context_parts = []
    for i, result in enumerate(results, start=1):
        context_parts.append(
            f"SOURCE {i} ({result['title']}):\n"
            f"URL: {result['url']}\n"
            f"Content: {result['content']}\n"
        )

    return "\n".join(context_parts)


def format_chat_history(chat_history_list):
    """
    Converts Pydantic objects or dicts from chat_history into a clean string block.
    Takes only the last 4 messages to preserve context without overwhelming the prompt.
    """
    if not chat_history_list:
        return "No prior conversation history."

    formatted = []
    for msg in chat_history_list:
        
        role = getattr(msg, "role", None) or (msg.get("role") if isinstance(msg, dict) else "User")
        content = getattr(msg, "content", None) or (msg.get("content") if isinstance(msg, dict) else "")
        role_label = "User" if str(role).lower() == "user" else "Assistant"
        formatted.append(f"{role_label}: {content}")

    return "\n".join(formatted[-4:])




prompt = PromptTemplate(
    template="""
You are "BIS Sahayak", an authentic, direct, and helpful AI assistant for the Bureau of Indian Standards (BIS).
Your goal is to answer questions naturally and conversationally, matching your response length directly to the user's request.

INTENT-BASED FORMATTING RULES:
1. YES/NO & BRIEF QUERIES (e.g., "Is this mandatory?", "What is the IS code?"):
   - Give a direct, concise 1-2 sentence answer immediately.
   - DO NOT use bullet points, long introductions, or detailed lists unless explicitly requested.
   - Example: "Yes, ISI certification under IS 17803:2022 is mandatory for manufacturing and selling steel water bottles in India."

2. DETAILED & PROCESS REQUESTS (e.g., "List the requirements", "How do I apply?", "Explain the steps"):
   - Use brief bullet points for clarity.
   - Keep points short and easily scannable.

3. CONVERSATIONAL TONE:
   - Lead directly with the answer in sentence 1. NEVER use robotic filler ("According to official sources...", "Here is a breakdown...").
   - Conclude natural responses with a single, relevant follow-up question to keep the conversation going smoothly.

4. CRITICAL LANGUAGE RULE:
   - Match the USER QUESTION language: English -> English, Devanagari Hindi -> Devanagari Hindi, Hinglish -> Roman script Hinglish.

PREVIOUS CHAT HISTORY:
{chat_history}

WEB EVIDENCE:
{context}

USER QUESTION:
{question}

ANSWER:
""",
    input_variables=["chat_history", "context", "question"]
)




def is_simple_greeting(question: str) -> bool:
    greetings = ["hi", "hello", "hey", "namaste", "good morning", "good evening"]
    return question.strip().lower() in greetings


def ask_question(user_question: str, chat_history_list=None):
    if chat_history_list is None:
        chat_history_list = []

    
    if is_simple_greeting(user_question):
        greeting_reply = "Namaste! I'm your BIS Sahayak assistant. How can I help you with Indian Standards, product certifications, or lab testing today?"
        return greeting_reply, []

    
    results, search_query = get_web_results(user_question)
    web_context = format_web_context(results)
    formatted_history = format_chat_history(chat_history_list)

    
    final_prompt = prompt.invoke({
        "chat_history": formatted_history,
        "context": web_context,
        "question": user_question
    })

    response = llm.invoke(final_prompt)
    answer = response.content.strip() if hasattr(response, "content") else str(response).strip()

    
    sources = []
    for result in results:
        url = result.get("url")
        if url and url not in sources:
            sources.append(url)

    return answer, sources