import os
from typing import List
from pydantic import BaseModel, Field
from tavily import TavilyClient
from dotenv import load_dotenv

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from app.config import llm

load_dotenv()
tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))


# 1. Pydantic Schemas
class StandardItem(BaseModel):
    standard_number: str = Field(description="The IS code number, e.g., 'IS 616:2017'")
    title: str = Field(description="Official title of the Indian Standard")
    category: str = Field(description="Product category, e.g., 'Electronics'")
    description: str = Field(description="Brief technical description or scope")
    relevance: str = Field(description="Compliance scope for the product")


class StandardsSearchResponse(BaseModel):
    success: bool = Field(description="True if matching IS standards were found")
    results: List[StandardItem] = Field(default_factory=list)


# 2. Setup Parser and Prompt
parser = PydanticOutputParser(pydantic_object=StandardsSearchResponse)

prompt = PromptTemplate(
    template="""You are an expert BIS Compliance Data Extractor.
Extract relevant Indian Standards (IS numbers) for the product query "{query}" from the search context below.

{format_instructions}

STRICT RULES:
- Only extract standards that explicitly match or apply to "{query}".
- Fill out all fields accurately according to the JSON instructions.
- If no valid Indian Standard is present in the context, return success=false and results=[].

Context:
{context}
""",
    input_variables=["query", "context"],
    partial_variables={"format_instructions": parser.get_format_instructions()}
)


# 3. Main Search Function
def search_bis_standards(user_query: str) -> dict:
    optimized_query = f"{user_query} Indian Standard IS code BIS mandatory category"
    
    try:
        response = tavily_client.search(
            query=optimized_query,
            search_depth="advanced",
            max_results=5
        )
        web_context_list = [f"[Source: {r['url']}]\n{r['content']}" for r in response.get("results", [])]
        web_context = "\n\n".join(web_context_list)
    except Exception:
        return {"success": False, "results": []}

    if not web_context.strip():
        return {"success": False, "results": []}

    # Chain execution
    chain = prompt | llm | parser
    
    try:
        parsed_result = chain.invoke({"query": user_query, "context": web_context})
        return parsed_result.model_dump()
    except Exception as e:
        print(f"Parsing error: {e}")
        return {"success": False, "results": []}