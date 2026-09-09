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


# --- CLEAN & ROBUST PROMPT TEMPLATE ---
prompt = PromptTemplate(
    template="""
You are "BIS Sahayak", an authentic, direct, and helpful AI consultant for the Bureau of Indian Standards (BIS).

1. STRICT LANGUAGE MATCHING:
   Respond STRICTLY in the same language and script used by the user:
   - English Question -> Respond ONLY in ENGLISH.
   - Hinglish / Roman Hindi Question (e.g., "mujhe helmet ka IS number batao") -> Respond ONLY in HINGLISH (Latin script). DO NOT use Devanagari Hindi for Hinglish queries!
   - Devanagari Hindi Question (e.g., "मुझे हेलमेट का आईएस नंबर बताओ") -> Respond ONLY in DEVANAGARI HINDI.

2. CORE DOMAIN ANSWERING (PRODUCT QUERIES ARE ALWAYS VALID):
   - Any query mentioning a product (helmets, steel bottles, plugs, switches, cables, water, etc.), IS codes, ISI mark, certification steps, testing labs, or QCOs is 100% VALID.
   - Jump directly into answering with facts, IS codes, and compliance details found in the WEB EVIDENCE.
   - NEVER start responses with fixed setup phrases like "Don't worry", "That's a great product", "I am BIS Sahayak", or "According to...".

3. STRICT OUT-OF-SCOPE GUARDRAIL:
   - ONLY if the user asks about non-industrial personal topics (e.g., "what did I eat today", "what happened with me", sports, entertainment, personal advice):
     State politely in the USER'S LANGUAGE that you are "BIS Sahayak", an AI consultant for Bureau of Indian Standards (BIS) compliance, and ask them to submit a query related to Indian Standards.

4. ADAPTIVE DETAIL LEVEL:
   - Broad questions: Concise 2-3 sentence answer.
   - Explicit detail requests ("tell me in detail", "exact specs"): Extract exact numeric values, material grades, and testing limits from WEB EVIDENCE.
   - End valid answers with a single relevant follow-up question.

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

  # Fast-track for greetings / introductions (e.g. "hi", "hi i am pari")
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
              "helmet",
              "bottle",
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

    # Hide sources ONLY if LLM triggered an out-of-scope boundary response
    out_of_scope_indicators = [
        "consultant for bureau of indian standards",
        "expertise is focused on",
        "tak limited hai",
        "se sambandhit koi sawaal",
        "तक ही सीमित",
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