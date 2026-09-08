import os
from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from tavily import TavilyClient

from app.config import llm

load_dotenv()

tavily_api_key = os.getenv("TAVILY_API_KEY")
if not tavily_api_key:
  raise ValueError("TAVILY_API_KEY is not set in your .env file.")

tavily_client = TavilyClient(api_key=tavily_api_key)


def get_web_results(user_question: str, max_results: int = 5):
  """Constructs targeted search queries to retrieve active, official BIS standards, QCOs, amendments, and detailed technical parameters."""
  
  detail_keywords = ""
  lowered = user_question.lower()
  if any(
      k in lowered
      for k in [
          "detail",
          "specification",
          "thickness",
          "limit",
          "parameter",
          "test",
          "material",
          "requirement",
          "grade",
      ]
  ):
    detail_keywords = "material grades testing parameters requirements limits"

  search_query = (
      f"Bureau of Indian Standards BIS active latest revision amended IS"
      f" standard QCO {user_question} {detail_keywords}"
  ).strip()

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
            "egazette.gov.in",
            "corpbiz.io",
            "alephindia.in",
        ],
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
      cleaned_results.append({"title": title, "url": url, "content": content})

  return cleaned_results, search_query


def format_web_context(results: list) -> str:
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


def format_chat_history(chat_history_list: list) -> str:
  """Converts Pydantic objects or dicts from chat_history into a clean string block.

  Takes the last 4 messages to preserve context without bloating the prompt.
  """
  if not chat_history_list:
    return "No prior conversation history."

  formatted = []
  for msg in chat_history_list:
    role = getattr(msg, "role", None) or (
        msg.get("role") if isinstance(msg, dict) else "User"
    )
    content = getattr(msg, "content", None) or (
        msg.get("content") if isinstance(msg, dict) else ""
    )
    role_label = "User" if str(role).lower() == "user" else "Assistant"
    formatted.append(f"{role_label}: {content}")

  return "\n".join(formatted[-4:])



# --- DYNAMIC & ADAPTIVE CONVERSATIONAL PROMPT TEMPLATE ---
prompt = PromptTemplate(
    template="""
You are "BIS Sahayak", an authentic, direct, and helpful AI consultant for the Bureau of Indian Standards (BIS).
Your primary focus is guiding users on Indian Standards (IS codes), ISI mark, CRS, Hallmarking, testing labs, Quality Control Orders (QCOs), and product compliance.

CRITICAL DIALOGUE RULES:

1. STRICT DOMAIN EVALUATION (IMPORTANT):
   - VALID DOMAIN QUERIES: Questions about any physical product (e.g., plugs, sockets, helmets, water, steel), manufacturing, quality standards, certification processes, testing, lab audits, or QCOs are VALID.
     -> DO NOT output any boundary/disclaimer warning for valid domain queries. Give the technical answer directly!
   - COMPLETELY UNRELATED QUERIES: Questions about personal life (e.g., "aaj maine kya khaya"), unrelated hobbies, sports, entertainment, or completely non-industrial topics are OUT-OF-SCOPE.
     -> ONLY for completely unrelated queries, respond politely: 
        "Main 'BIS Sahayak' hoon, aur meri expertise Bureau of Indian Standards (BIS), IS codes, aur product compliance tak limited hai. Kripya BIS certification ya Indian Standards se sambandhit koi sawaal poochein!"

2. DYNAMIC OPENINGS (NO FIXED PREFIXES): For valid domain queries, NEVER start responses with fixed phrases like "Don't worry", "That's a great product", "According to...", or "I am BIS Sahayak". Jump directly into the factual answer.

3. ADAPTIVE DETAIL LEVEL:
   - For general queries ("What is the standard for plug and socket?"): Provide a concise 2-sentence direct answer.
   - For explicit detail requests ("Tell me in detail", "What are the exact testing parameters?"): List exact material grades, dimensions, and numeric parameters found in the WEB EVIDENCE.

4. TONE & REPETITION GUARD:
   - Match the user's language (English -> English, Devanagari Hindi -> Devanagari Hindi, Hinglish -> Hinglish).
   - When using Hinglish, use clean everyday conversational sentences. NEVER repeat or loop technical phrases.

5. GUIDING FOLLOW-UP QUESTION: For valid queries, end with a single, relevant follow-up question (e.g., asking about current production scale, location, or specific product variant).

PREVIOUS CHAT HISTORY:
{chat_history}

WEB EVIDENCE:
{context}

USER QUESTION:
{question}

ANSWER:
""",
    input_variables=["chat_history", "context", "question"],
)


def is_simple_greeting(question: str) -> bool:
  greetings = [
      "hi",
      "hello",
      "hey",
      "namaste",
      "good morning",
      "good evening",
      "haa",
      "haan",
  ]
  return question.strip().lower() in greetings


def ask_question(user_question: str, chat_history_list=None):
  if chat_history_list is None:
    chat_history_list = []

  if is_simple_greeting(user_question):
    greeting_reply = (
        "Namaste! I'm your BIS Sahayak assistant. What product or"
        " certification are you working on today? I'd love to help you get"
        " started!"
    )
    return greeting_reply, []

  results, search_query = get_web_results(user_question)
  web_context = format_web_context(results)
  formatted_history = format_chat_history(chat_history_list)

  final_prompt = prompt.invoke({
      "chat_history": formatted_history,
      "context": web_context,
      "question": user_question,
  })

  response = llm.invoke(final_prompt)
  answer = (
      response.content.strip()
      if hasattr(response, "content")
      else str(response).strip()
  )

  sources = []
  for result in results:
    url = result.get("url")
    if url and url not in sources:
      sources.append(url)

  return answer, sources