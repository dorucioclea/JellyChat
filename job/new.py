import os
import re
from langchain.vectorstores import SupabaseVectorStore
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from supabase.client import Client, create_client
from dotenv import load_dotenv
import uuid

from defichainpython_loader import DefichainPythonLoader
from sitemap_parser import get_urls

load_dotenv()

vectorTableName = "embeddings"
scrapeUrls = ["https://docs.defichain-python.de/build/html/sitemap.xml"]
chunk_size = 1000
chunk_overlap = 50
embedding_model = "text-embedding-ada-002"

supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

urls = []

# Get all urls from sitemap
for url in scrapeUrls:
    urls.extend(get_urls(url))
print("🔎 Found %s pages in total" % len(urls))

# Remove duplicates
urls = list(dict.fromkeys(urls))
print("🔎 Found %s unique pages" % len(urls))


# Remove urls
remove_urls = (
    "https://docs.defichain-python.de/build/html/search.html"
)

urls = [url for url in urls if url not in remove_urls]

print("🔭 Scrape %s found pages.." % len(urls))
print("---")
docs = []
for url in urls:
    loader = DefichainPythonLoader(url)
    docs.extend(loader.load())

print(f"✅ Scraped all pages")

for doc in docs:
    print("🌐 Source:", doc.metadata["source"])
    print("🔖 Title:", doc.metadata["title"])
    print("📄 Content:", doc.page_content.replace("\n", " ")[:100] + "...")
    print("---")

print("➖ Remove long strings")
for document in docs:
    document.page_content = re.sub(
        r"(?<=\S)[^\s]{" + str(chunk_size) + ",}(?=\S)", "", document.page_content
    )
print("✅ Removed long strings")


print("🗨 Split into chunks..")
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=chunk_size,
    chunk_overlap=chunk_overlap,
    length_function=len,
    separators=["\n\n", "\n", " ", ""],
)
docs = text_splitter.split_documents(docs)
print("✅ Split into %s chunks" % len(docs))

# import tiktoken

# enc = tiktoken.get_encoding("cl100k_base")
# for doc in docs:
#     print("🔖 Title:", doc.metadata["title"])
#     print("📄 Content:", doc.page_content.replace("\n", " ")[:100] + "...")
#     tokens = enc.encode(doc.page_content)
#     print("⚡ Tokens:", len(tokens))

print("➖ Remove all old documents from table")
supabase.table(vectorTableName).delete().neq("id", uuid.uuid1()).execute()
print("✅ Removed all old documents from table")

print("🔮 Embedding..")
embeddings = OpenAIEmbeddings(model=embedding_model)
upload_chunk_size = 200

# Split the documents in chunks for upload (Did time out when too large).
docs_chunks = [
    docs[x : x + upload_chunk_size] for x in range(0, len(docs), upload_chunk_size)
]

# Iterate over each chunk and upload separately.
for doc_chunk in docs_chunks:
    vector_store = SupabaseVectorStore.from_documents(
        doc_chunk,
        embeddings,
        client=supabase,
        table_name=vectorTableName,
    )
print("✅ Embedded")
