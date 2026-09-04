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


# ============================================================
# TAVILY WEB SEARCH ENGINE
# ============================================================

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


# ============================================================
# CONTEXT FORMATTER
# ============================================================

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


# ============================================================
# DYNAMIC, MULTILINGUAL & CONVERSATIONAL PROMPT
# ============================================================

prompt = PromptTemplate(
    template="""
You are BIS Sahayak, an expert assistant for the Bureau of Indian Standards (BIS).

Answer the user's question using ONLY the provided web evidence.

CRITICAL LANGUAGE RULE:
- Look ONLY at the USER QUESTION to determine the output language. Ignore the language of the web context.
- If the USER QUESTION is written in English -> You MUST answer 100% in pure English.
- If the USER QUESTION is written in Devanagari Hindi -> You MUST answer in Devanagari Hindi.
- If the USER QUESTION is written in Hinglish (Roman script Hindi) -> You MUST answer in Hinglish.

ANSWER FORMATTING & LENGTH:
- Default Behavior: Keep simple questions direct and brief (2 to 3 sentences max).
- Detailed Requests: If the user explicitly asks for "requirements", "details", "description", "process", or "specifications", provide a clear, structured bulleted list based on the evidence.
- Always include active IS standard numbers with revision years (e.g., IS 14756:2024).
- Do NOT include raw web links or URLs inside your answer body text.
- If evidence is insufficient, politely state in the user's language that official sources do not contain clear information.

WEB EVIDENCE:
{context}

USER QUESTION:
{question}

ANSWER:
""",
    input_variables=["context", "question"]
)


# ============================================================
# API INFERENCE ENGINE
# ============================================================

def ask_question(user_question):
    # Retrieve web evidence
    results, search_query = get_web_results(user_question)
    web_context = format_web_context(results)

    # Format final prompt and invoke LLM
    final_prompt = prompt.invoke({
        "context": web_context,
        "question": user_question
    })

    response = llm.invoke(final_prompt)
    answer = response.content.strip()

    # Extract unique source URLs for backend API JSON response
    sources = []
    for result in results:
        url = result.get("url")
        if url and url not in sources:
            sources.append(url)

    return answer, sources