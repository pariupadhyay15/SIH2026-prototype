import os
from typing import List
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from tavily import TavilyClient

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate

# Import your initialized LLM instance from your app config
from app.config import llm

load_dotenv()

# Initialize Tavily Client
tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))


# 1. Pydantic Schemas matching the backend API contract
class StandardItem(BaseModel):
    standard_number: str = Field(description="The IS code number, e.g., 'IS 616:2017' or 'IS 4151:2015'")
    title: str = Field(description="Official title of the Indian Standard")
    category: str = Field(description="Product category, e.g., 'Electronics', 'Automotive', 'Personal Protective Equipment'")
    description: str = Field(description="Brief technical description or scope of the standard")
    relevance: str = Field(description="Why this standard applies to the queried item and its compliance scope")


class StandardsSearchResponse(BaseModel):
    success: bool = Field(description="True if matching IS standards were found, False otherwise")
    results: List[StandardItem] = Field(default_factory=list, description="List of matching Indian Standards")


# 2. Setup Pydantic Output Parser and Dynamic Prompt
parser = PydanticOutputParser(pydantic_object=StandardsSearchResponse)

prompt = PromptTemplate(
    template="""You are an expert BIS Compliance Data Extractor.
Extract relevant Indian Standards (IS numbers) for the query "{query}" from the search context below.

{format_instructions}

STRICT RULES:
- If "{query}" is a product name (e.g., "helmet", "headphones"), list all relevant standards for that product.
- If "{query}" is an IS standard number (e.g., "IS 4151", "4151", "IS 616"), extract full details specifically for that standard.
- Only extract standards that explicitly match or apply to "{query}".
- Fill out all fields accurately according to the JSON instructions.
- If no valid Indian Standard is present in the context, return success=false and results=[].

Context:
{context}
""",
    input_variables=["query", "context"],
    partial_variables={"format_instructions": parser.get_format_instructions()}
)


# 3. Main Web Search & Extraction Function
def search_bis_standards(user_query: str) -> dict:
    user_query_clean = user_query.strip().upper()

    # Dynamic Search Query Routing (Product Name vs IS Standard Code)
    if "IS" in user_query_clean or any(char.isdigit() for char in user_query_clean):
        optimized_query = f"Bureau of Indian Standards {user_query_clean} product scope category"
    else:
        optimized_query = f"{user_query} Indian Standard IS code BIS mandatory category"

    # Fetch live web snippets using Tavily
    try:
        response = tavily_client.search(
            query=optimized_query,
            search_depth="advanced",
            max_results=5
        )
        web_context_list = [f"[Source: {r['url']}]\n{r['content']}" for r in response.get("results", [])]
        web_context = "\n\n".join(web_context_list)
    except Exception as e:
        print(f"Tavily Search Error: {e}")
        return {"success": False, "results": []}

    if not web_context.strip():
        return {"success": False, "results": []}

    # Execute LCEL Chain (Prompt | LLM | Parser)
    chain = prompt | llm | parser

    try:
        parsed_result = chain.invoke({"query": user_query, "context": web_context})
        return parsed_result.model_dump()
    except Exception as e:
        print(f"Parsing error in search_bis_standards: {e}")
        return {"success": False, "results": []}