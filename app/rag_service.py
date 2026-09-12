import difflib
import os
import re
from urllib.parse import urlparse
from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from tavily import TavilyClient

from app.config import llm


TRUSTED_DOMAINS = {
    "bis.gov.in",
    "standards.bis.gov.in",
    "manakonline.in",
    "crsbis.in",
    "pib.gov.in",
    "egazette.gov.in",
    "corpbiz.io",
    "alephindia.in",
    "consumeraffairs.gov.in",   
    "consumeraffairs.nic.in",   
    "ncdrc.nic.in",             
    "qcin.org",                 
    "india.gov.in",             
}

load_dotenv()

tavily_api_key = os.getenv("TAVILY_API_KEY")
if not tavily_api_key:
  raise ValueError("TAVILY_API_KEY is not set in your .env file.")

tavily_client = TavilyClient(api_key=tavily_api_key)



def detect_language(text: str) -> str:
  """Returns 'devanagari', 'hinglish', or 'english' based on the user's own text."""
  if re.search(r"[\u0900-\u097F]", text):
    return "devanagari"

  hinglish_words = [
      "kya", "hai", "kaise", "kyun", "nahi", "nahin", "mujhe", "matlab",
      "aapko", "chahiye", "batao", "karna", "karo", "hoga", "kar", "mera",
      "meri", "iske", "iska", "yeh", "ye", "sahi", "galat",
  ]
  lowered = text.lower()
  hits = sum(1 for w in hinglish_words if re.search(rf"\b{w}\b", lowered))
  if hits >= 2:
    return "hinglish"

  return "english"



SCENARIO_KEYWORDS = [
    
    "no record found", "fake", "fraud", "cheated", "scam", "duplicate",
    "not working", "denied", "rejected", "complaint", "problem", "issue",
    "missing", "lost", "damaged", "refused", "wrong", "expired", "invalid",
    "doesn't match", "not matching", "mismatch", "broke", "broken", "crack",
    "cracked", "return", "refund", "leak", "leaking",
    
    "nakli", "asli", "shikayat", "galat", "kharab", "toot", "tut gaya",
    "kaam nahi", "chal nahi raha", "dhoka", "jhooth", "fatt gaya",
    "khareeda", "wapas", "paisa wapas", "lifafa",
    
    "नकली", "असली", "शिकायत", "खराब", "टूट", "काम नहीं", "धोखा", "वापस",
]


def is_scenario_query(question: str) -> bool:
  lowered = question.lower()
  return any(k in lowered for k in SCENARIO_KEYWORDS)


PRONOUN_FOLLOWUP_HINTS = [
    "it", "this", "that", "iske", "iska", "isse", "isko", "uska", "usse",
    "usme", "isme", "wo", "vo", "wahi", "vahi", "us", "yah", "ismein",
]


def looks_like_followup(question: str) -> bool:
  """Heuristic: short question relying on a pronoun from earlier context."""
  lowered = question.lower()
  word_count = len(lowered.split())
  has_pronoun = any(
      re.search(rf"\b{p}\b", lowered) for p in PRONOUN_FOLLOWUP_HINTS
  )
  return has_pronoun and word_count <= 12


def _last_user_turn(chat_history_list: list):
  """Pulls the most recent user message from history, for follow-up context."""
  for msg in reversed(chat_history_list or []):
    role = getattr(msg, "role", None) or (
        msg.get("role") if isinstance(msg, dict) else None
    )
    if str(role).lower() == "user":
      return getattr(msg, "content", None) or (
          msg.get("content") if isinstance(msg, dict) else None
      )
  return None


def _normalize_url(url: str) -> str:
  """Strips query string/fragment so '?lang=en' variants dedupe as one page."""
  parsed = urlparse(url)
  return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")


def get_web_results(
    user_question: str, chat_history_list: list = None, max_results: int = 5
):
  """Constructs targeted search queries to retrieve active, official BIS standards, QCOs, amendments, technical parameters, and grievance/redressal procedures."""

  lowered = user_question.lower()

  detail_keywords = ""
  if any(
      k in lowered
      for k in [
          "detail", "specification", "thickness", "limit", "parameter",
          "test", "material", "requirement", "grade",
      ]
  ):
    detail_keywords = "material grades testing parameters requirements limits"

  scenario_keywords = ""
  if is_scenario_query(user_question):
    scenario_keywords = (
        "complaint grievance redressal CGRC consumer complaint BIS Care app"
        " helpline procedure how to report"
    )


  context_hint = ""
  if looks_like_followup(user_question):
    last_turn = _last_user_turn(chat_history_list)
    if last_turn:
      context_hint = last_turn

  search_query = (
      f"Bureau of Indian Standards BIS active latest revision amended IS"
      f" standard QCO {context_hint} {user_question} {detail_keywords}"
      f" {scenario_keywords}"
  ).strip()
  search_query = re.sub(r"\s+", " ", search_query)

  try:
    response = tavily_client.search(
        query=search_query,
        search_depth="advanced",
        max_results=max_results,
        include_domains=list(TRUSTED_DOMAINS),
    )
  except Exception as e:
    print(f"Tavily search error, retrying once: {e}")
    try:
      response = tavily_client.search(
          query=search_query,
          search_depth="basic",  
          max_results=max_results,
          include_domains=list(TRUSTED_DOMAINS),
      )
    except Exception as e2:
      print(f"Tavily search failed on retry: {e2}")
      return [], search_query

  results = response.get("results", [])
  cleaned_results = []
  seen_urls = set()

  for result in results:
    title = result.get("title", "").strip()
    url = result.get("url", "").strip()
    content = result.get("content", "").strip()

    if not (title and url and content):
      continue

    
    domain = urlparse(url).netloc.lower().lstrip("www.")
    if not any(domain == d or domain.endswith("." + d) for d in TRUSTED_DOMAINS):
      continue

    normalized = _normalize_url(url)
    if normalized in seen_urls:
      continue
    seen_urls.add(normalized)

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

  return "\n".join(formatted[-8:])  # last 4 exchanges (user+assistant pairs)



prompt = PromptTemplate(
    template="""
You are "BIS Sahayak", a warm, direct, and knowledgeable human consultant for the Bureau of Indian Standards (BIS). You talk like a helpful person, not a search engine — you never restate the question or repeat the same point twice.

1. LANGUAGE — NON-NEGOTIABLE:
   The user's detected language is: {language}
   - If "english" -> reply ONLY in English.
   - If "hinglish" -> reply ONLY in Hinglish (Roman/Latin script Hindi). NEVER use Devanagari script.
   - If "devanagari" -> reply ONLY in Devanagari Hindi.
   Match this exactly, regardless of what language the WEB EVIDENCE is in.

2. NO REPETITION — CRITICAL:
   - Every sentence must add NEW information. Never restate the user's problem back to them, never repeat the same fact in two different sentences, never end by asking the same thing you already answered.
   - Do not begin with filler like "Don't worry", "That's a great question", "According to...", or any self-introduction ("I am BIS Sahayak...").
   - No greetings ("Namaste!", "Hello!") unless the user's message is only a greeting.

3. REAL-LIFE SCENARIO / PROBLEM QUERIES (e.g. "I checked and it says no record found", "seller refused to refund", "I think this is fake"):
   Answer like a person who has actually helped others through this before:
   - Start with a one-line, direct answer to what they're actually worried about (e.g. whether it's fake, whether they're at risk) — don't hedge with "it cannot be said" without also saying what it usually means in practice.
   - Give 3-5 concrete, ordered next steps (what to check, where to verify, who to contact — app names, portals, helpline, or complaint body if relevant from WEB EVIDENCE or general BIS process knowledge).
   - Mention realistic possibilities in plain terms (e.g. a mistyped code, an unregistered/fake mark, a portal delay) instead of only saying "more information is needed."
   - End with ONE forward-moving follow-up question that helps decide the NEXT piece of advice to give (e.g. "have you already re-checked the code for a typo?", "do you want the steps to file a formal complaint if it turns out fake?"). NEVER ask the user to hand over case details you cannot act on (their purchase date, the seller's contact number, personal documents) — you cannot contact anyone or file anything on their behalf, so asking for that is misleading. Only ask things that change what you'd say next.

4. CORE DOMAIN ANSWERING (PRODUCT QUERIES ARE ALWAYS VALID):
   - Any query about products (helmets, steel bottles, plugs, switches, cables, gold/jewellery hallmarking, water, etc.), IS codes, ISI/HUID marks, certification steps, testing labs, or QCOs is 100% valid.
   - Jump directly into facts, IS codes, and compliance details from the WEB EVIDENCE.

5. STRICT OUT-OF-SCOPE GUARDRAIL:
   - ONLY if the question is a non-industrial personal topic unrelated to BIS/standards/certification (e.g. sports, entertainment, personal life advice, coding help, general chit-chat with no product/standard/certification angle):
     Your response must start with the exact tag "OUT_OF_SCOPE_FLAG" as the very first characters (nothing before it), then a newline, then your polite message in the user's language saying you are BIS Sahayak, an AI consultant for BIS compliance, and asking them to ask something related to Indian Standards.
   - Do NOT add this tag in any other case, including scenario/complaint questions about a product — those are always in scope.

6. ADAPTIVE DETAIL LEVEL:
   - Broad questions: 2-4 sentence answer.
   - Explicit detail requests ("in detail", "exact specs"): extract exact numeric values, material grades, and testing limits from WEB EVIDENCE.
   - Scenario/complaint questions: use the numbered-steps format from rule 3, not a plain paragraph.

7. PRECISION — NEVER GUESS A NUMBER, BUT NEVER DEFLECT ONE YOU HAVE EITHER:
   - Never state a specific IS number, QCO number, or numeric limit (thickness, pH, TDS, etc.) unless it appears verbatim in the WEB EVIDENCE. Do not recall one from general memory and present it as current or confirmed.
   - If the WEB EVIDENCE does not contain the specific number needed, say plainly that you can't confirm the exact number from available sources, and point to where they can look it up (BIS "Know Your Standard" portal, or the relevant product page).
   - BUT: if the number IS present in the WEB EVIDENCE, state it as a confident, final fact. Do NOT hedge a sourced answer with "please verify on the BIS website," "check the latest version yourself," "contact BIS directly," or similar — you ARE the tool the user is using instead of digging through the BIS site themselves; redirecting them back to it defeats the purpose. You may add ONE brief factual note if genuinely useful (e.g. the standard's year, or that a specific part/scope applies), but never as a suggestion for the user to go re-check what you just told them.
   - Do not tack on a generic follow-up question to a plain factual answer that doesn't need one ("would you like to confirm this further?"). Only ask a follow-up when it's the rule-3 scenario format, or when something genuinely still needs to be decided (e.g. which of two variants applies to their case).

EXAMPLES OF THE RIGHT SHAPE FOR A SCENARIO ANSWER (do not copy the content, only the shape — no echoed question, no repeated sentences, no dead-end filler):

Example (English): "That result usually means one of two things: the code was mistyped, or the mark itself was never registered — it doesn't automatically mean fraud. Steps: 1) Re-check the digits on the bill against the digits on the jewellery itself. 2) Retry verification on the BIS Care app after confirming the digits. 3) If it still fails, ask the jeweller for the Assaying and Hallmarking Centre's registration proof. 4) If they can't produce it, file a complaint through the BIS Care app or the BIS helpline. Do you want the direct steps for filing that complaint?"

Example (Hinglish): "Yeh zaroori nahi ki fake ho — zyadatar cases mein ya toh code galat type hua hota hai, ya mark register hi nahi tha. Steps: 1) Bill aur cooker dono par number match karo. 2) BIS website par manufacturer ka certification check karo. 3) Agar certification nahi milta, dukaandar se ISI license number maango. 4) Phir bhi doubt ho to BIS helpline par complaint file karo. Kya aapko complaint file karne ke exact steps chahiye?"

PREVIOUS CHAT HISTORY:
{chat_history}

WEB EVIDENCE:
{context}

USER QUESTION:
{question}

ANSWER:
""",
    input_variables=["chat_history", "context", "question", "language"],
)


def is_simple_greeting(question: str):
  q = question.strip().lower()

  greeting_patterns = [
      r"^(hi|hello|hey|namaste|good morning|good evening)\b"
  ]
  farewell_patterns = [
      r"^(bye|goodbye|bye bye|thank you|thanks|thanku|ok bye|shukriya)\b"
  ]

  if (
      any(re.search(pat, q) for pat in greeting_patterns)
      and len(q) < 35
      and not any(
          k in q
          for k in [
              "standard", "is", "code", "bis", "certificate", "license",
              "test", "helmet", "bottle",
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


def _split_sentences(text: str) -> list:
  
  parts = re.split(r"(?<=[.!?।])\s+", text.strip())
  return [p for p in parts if p.strip()]


def clean_repetition(answer: str, user_question: str) -> str:
  """Code-level safety net: strips an echoed opening question and drops any
  sentence that's a near-duplicate of one already said. Independent of
  whether the LLM actually follows the no-repetition prompt rule."""
  sentences = _split_sentences(answer)
  if not sentences:
    return answer

  
  first_vs_question = difflib.SequenceMatcher(
      None, sentences[0].lower(), user_question.lower()
  ).ratio()
  if first_vs_question > 0.6:
    sentences = sentences[1:]

  kept = []
  for sentence in sentences:
    is_dupe = any(
        difflib.SequenceMatcher(None, sentence.lower(), prior.lower()).ratio()
        > 0.75
        for prior in kept
    )
    if not is_dupe:
      kept.append(sentence)

  cleaned = " ".join(kept).strip()
  return cleaned if cleaned else answer


def ask_question(user_question: str, chat_history_list=None):
  if chat_history_list is None:
    chat_history_list = []

  is_shortcut, shortcut_response = is_simple_greeting(user_question)
  if is_shortcut:
    return shortcut_response, []

  try:
    language = detect_language(user_question)
    results, search_query = get_web_results(user_question, chat_history_list)
    web_context = format_web_context(results)
    formatted_history = format_chat_history(chat_history_list)

    final_prompt = prompt.invoke({
        "chat_history": formatted_history,
        "context": web_context,
        "question": user_question,
        "language": language,
    })

    response = llm.invoke(final_prompt)
    answer = (
        response.content.strip()
        if hasattr(response, "content")
        else str(response).strip()
    )

    if answer.strip().startswith("OUT_OF_SCOPE_FLAG"):
      answer = answer.strip().replace("OUT_OF_SCOPE_FLAG", "", 1).lstrip("\n ").strip()
      sources = []
    else:
      answer = clean_repetition(answer, user_question)
      sources = [r.get("url") for r in results if r.get("url")]
      sources = list(dict.fromkeys(sources))  # dedupe, keep order

    return answer, sources

  except Exception as e:
    print(f"Error executing ask_question: {e}")
    return (
        "I experienced a temporary issue processing your request. Please try"
        " asking your question again!"
    ), []