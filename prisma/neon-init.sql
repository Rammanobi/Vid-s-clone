-- 1. Enable pgvector Extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Create HNSW Index for Dense Vector Similarity Search
CREATE INDEX IF NOT EXISTS reel_embedding_hnsw_idx 
ON "Reel" 
USING hnsw ("combinedEmbedding" vector_cosine_ops);

-- 3. Create GIN Index for BM25 Keyword Sparse Search
CREATE INDEX IF NOT EXISTS reel_sparse_bm25_idx 
ON "Reel" 
USING gin ("searchVector");

-- 4. Create Automatic tsvector Search Vector Sync Trigger
CREATE OR REPLACE FUNCTION update_reel_search_vector() RETURNS trigger AS $$
begin
  new."searchVector" :=
    setweight(to_tsvector('english', coalesce(new.caption, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(new.transcript, '')), 'B') ||
    setweight(to_tsvector('english', coalesce(new."visualSummary", '')), 'C');
  return new;
end
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS reel_search_vector_update ON "Reel";
CREATE TRIGGER reel_search_vector_update BEFORE INSERT OR UPDATE
ON "Reel" FOR EACH ROW EXECUTE FUNCTION update_reel_search_vector();