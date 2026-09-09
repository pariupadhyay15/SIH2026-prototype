import os
import re
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


# --- DYNAMIC PROMPT TEMPLATE ---
prompt = PromptTemplate(
    template="""
You are "BIS Sahayak", an authentic, direct, and helpful AI consultant for the Bureau of Indian Standards (BIS).
Your primary focus is guiding users on Indian Standards (IS codes), ISI mark, CRS, Hallmarking, testing labs, Quality Control Orders (QCOs), and product compliance.

CRITICAL DIALOGUE RULES:

1. STRICT LANGUAGE MATCHING RULE (MOST IMPORTANT):
   Detect the language/script of the USER QUESTION and respond STRICTLY in the exact same language/script:
   - If User wrote in ENGLISH -> Respond ONLY in pure ENGLISH.
   - If User wrote in HINGLISH/ROMAN HINDI -> Respond ONLY in HINGLISH.
   - If User wrote in DEVANAGARI HINDI -> Respond ONLY in DEVANAGARI HINDI.

2. STRICT DOMAIN EVALUATION:
   - GREETINGS & INTRODUCTIONS: If the user greets or introduces themselves (e.g., "Hi", "I am Pari"), greet them warmly and ask how you can help with BIS certification today. Do NOT treat introductions as out-of-scope.
   - VALID DOMAIN QUERIES: Questions about physical products, manufacturing, quality standards, certification processes, testing, lab audits, or QCOs are VALID. Answer directly and factually.
   - COMPLETELY UNRELATED QUERIES: Questions about personal life (e.g., "what happened with me today"), unrelated hobbies, sports, or non-industrial topics are OUT-OF-SCOPE.
     -> State politely in the USER'S LANGUAGE that you are "BIS Sahayak", an AI assistant specialized strictly in Bureau of Indian Standards (BIS) certification, IS codes, and compliance, and ask them to submit a query related to Indian Standards.

3. DYNAMIC OPENINGS (NO FIXED PREFIXES): For valid domain queries, NEVER start responses with fixed phrases like "Don't worry", "That's a great product", "According to...", or "I am BIS Sahayak". Jump directly into the factual answer.

4. ADAPTIVE DETAIL LEVEL:
   - For general queries: Provide a concise 2-sentence direct answer.
   - For explicit detail requests ("Tell me in detail", "What are the exact testing parameters?"): List exact material grades, dimensions, and numeric parameters found in WEB EVIDENCE.

5. GUIDING FOLLOW-UP QUESTION: For valid technical queries, end with a single, relevant follow-up question. For out-of-scope queries, DO NOT ask technical follow-up questions.

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


def is_simple_greeting(question: str):
  q = question.strip().lower()

  greeting_patterns = [
      r"^(hi|hello|hey|namaste|good morning|good evening)\b"
  ]
  farewell_patterns = [
      r"^(bye|goodbye|bye bye|thank you|thanks|thanku|ok bye|shukriya)\b"
  ]

  # Smart match for greetings/introductions like "hi", "hi i am pari", "hello my name is rahul"
  if (
      any(re.search(pat, q) for pat in greeting_patterns)
      and len(q) < 35
      and not any(
          k in q
          for k in [
              "standard",
              "is",
              "code",
              "bis",
              "certificate",
              "license",
              "test",
          ]
      )
  ):

    name_match = re.search(
        r"(?:i am|i'm|my name is|main)\s+([a-zA-Z]+)", q, re.IGNORECASE
    )
    user_name = f" {name_match.group(1).capitalize()}" if name_match else ""

    return True, (
        f"Namaste{user_name}! I'm your BIS Sahayak assistant. What product or"
        " certification are you working on today? I'd love to help you get"
        " started!"
    )

  if any(re.search(pat, q) for pat in farewell_patterns) and len(q) < 25:
    return True, (
        "Thank you for consulting BIS Sahayak! Feel free to return whenever you"
        " need assistance with Indian Standards or certification. Have a great"
        " day!"
    )

  return False, None


def ask_question(user_question: str, chat_history_list=None):
  if chat_history_list is None:
    chat_history_list = []

  # Instant check for greetings & farewells
  is_shortcut, shortcut_response = is_simple_greeting(user_question)
  if is_shortcut:
    return shortcut_response, []

  try:
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

    # Detect out-of-scope keywords across English, Hinglish, and Hindi to hide sources
    out_of_scope_indicators = [
        "limited",
        "specialized",
        "expertise is focused",
        "tak limited",
        "se sambandhit",
        "तक ही सीमित",
        "विशेषज्ञता",
    ]

    if any(ind in answer.lower() for ind in out_of_scope_indicators):
      sources = []
    else:
      sources = [r.get("url") for r in results if r.get("url")]
      sources = list(set(sources))

    return answer, sources

  except Exception as e:
    print(f"Error executing ask_question: {e}")
    return (
        "I experienced a temporary issue processing your request. Please try"
        " asking your question again!"
    ), []