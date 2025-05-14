import os
from typing import List, Dict
import chromadb
from chromadb.utils import embedding_functions
import google.generativeai as genai
from PyPDF2 import PdfReader
import re
from tqdm import tqdm

class GeminiChromaRAG:
    def __init__(self, api_key: str = None, persist_directory: str = "chroma_db"):
        """
        初始化 RAG 系統
        
        Args:
            api_key: Google API 密鑰
            persist_directory: 向量存儲的持久化目錄
        """
        if api_key is None:
            api_key = os.getenv("GOOGLE_API_KEY")
            if api_key is None:
                raise ValueError("請提供 Google API 密鑰或設置 GOOGLE_API_KEY 環境變量")
        
        # 配置 Gemini API
        genai.configure(api_key=api_key)
        
        # 自定義 Gemini 嵌入函數
        class GeminiEmbeddingFunction(embedding_functions.EmbeddingFunction):
            def __init__(self):
                self.model = "models/embedding-001"
            
            def __call__(self, texts: List[str]) -> List[List[float]]:
                embeddings = []
                for text in texts:
                    result = genai.embed_content(
                        model=self.model,
                        content=text,
                        task_type="retrieval_document"
                    )
                    embeddings.append(result["embedding"])
                return embeddings
        
        # 初始化 ChromaDB 客戶端
        self.client = chromadb.PersistentClient(path=persist_directory)
        
        # 創建集合
        self.collection = self.client.get_or_create_collection(
            name="documents",
            embedding_function=GeminiEmbeddingFunction()
        )
    
    def _extract_text_from_pdf(self, pdf_path: str) -> List[Dict]:
        """
        從 PDF 文件中提取文本
        
        Args:
            pdf_path: PDF 文件路徑
            
        Returns:
            包含文本和元數據的字典列表
        """
        try:
            reader = PdfReader(pdf_path)
            documents = []
            
            for page_num, page in enumerate(reader.pages):
                text = page.extract_text()
                if text.strip():  # 確保頁面不是空的
                    documents.append({
                        "text": text,
                        "metadata": {
                            "source": os.path.basename(pdf_path),
                            "page": page_num + 1
                        }
                    })
            
            return documents
        except Exception as e:
            raise Exception(f"處理 PDF 文件時出錯: {str(e)}")
    
    def _split_text(self, text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> List[str]:
        """
        將文本分割成較小的塊
        
        Args:
            text: 要分割的文本
            chunk_size: 塊的大小
            chunk_overlap: 塊之間的重疊大小
            
        Returns:
            文本塊列表
        """
        # 使用多個分隔符進行分割
        separators = ["\n\n", "\n", "。", "！", "？", ".", "!", "?", " ", ""]
        chunks = []
        
        # 首先按段落分割
        paragraphs = re.split(r'\n\s*\n', text)
        current_chunk = ""
        
        for paragraph in paragraphs:
            if len(current_chunk) + len(paragraph) <= chunk_size:
                current_chunk += paragraph + "\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = paragraph + "\n"
                
                # 如果段落太長，需要進一步分割
                if len(paragraph) > chunk_size:
                    words = paragraph.split()
                    temp_chunk = ""
                    for word in words:
                        if len(temp_chunk) + len(word) + 1 <= chunk_size:
                            temp_chunk += word + " "
                        else:
                            chunks.append(temp_chunk.strip())
                            temp_chunk = word + " "
                    if temp_chunk:
                        chunks.append(temp_chunk.strip())
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        # 處理重疊
        if chunk_overlap > 0:
            overlapped_chunks = []
            for i in range(len(chunks)):
                if i > 0:
                    # 添加前一個塊的結尾部分
                    prev_chunk = chunks[i-1]
                    overlap_text = prev_chunk[-chunk_overlap:] if len(prev_chunk) > chunk_overlap else prev_chunk
                    overlapped_chunks.append(overlap_text + chunks[i])
                else:
                    overlapped_chunks.append(chunks[i])
            chunks = overlapped_chunks
        
        return chunks
    
    def add_pdf(self, pdf_path: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> None:
        """
        處理 PDF 文件並添加到向量存儲
        
        Args:
            pdf_path: PDF 文件路徑
            chunk_size: 文本塊大小
            chunk_overlap: 文本塊重疊大小
        """
        # 提取文本
        documents = self._extract_text_from_pdf(pdf_path)
        
        # 處理每個文檔
        all_chunks = []
        all_metadatas = []
        
        for doc in tqdm(documents, desc="處理文檔"):
            # 分割文本
            chunks = self._split_text(doc["text"], chunk_size, chunk_overlap)
            
            # 為每個塊創建元數據
            for i, chunk in enumerate(chunks):
                all_chunks.append(chunk)
                all_metadatas.append({
                    "source": doc["metadata"]["source"],
                    "page": doc["metadata"]["page"],
                    "chunk_id": i
                })
        
        # 添加到向量存儲
        if all_chunks:
            self.collection.add(
                documents=all_chunks,
                metadatas=all_metadatas,
                ids=[f"{doc['metadata']['source']}_{i}" for i in range(len(all_chunks))]
            )
    
    def search(self, query: str, n_results: int = 5) -> Dict:
        """
        搜索相似文檔
        
        Args:
            query: 查詢文本
            n_results: 返回結果數量
            
        Returns:
            包含文檔和相似度的結果字典
        """
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            include=["documents", "metadatas", "distances"]
        )
        
        # 格式化結果
        formatted_results = []
        for i in range(len(results["documents"][0])):
            formatted_results.append({
                "content": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "similarity": 1 / (1 + results["distances"][0][i])
            })
            
        return formatted_results
    
    def format_context(self, results: List[Dict]) -> str:
        """
        格式化檢索結果為模型可用的上下文
        
        Args:
            results: 檢索結果列表
            
        Returns:
            格式化後的上下文字符串
        """
        if not results:
            return "未找到相關文獻。"
            
        context_parts = []
        for i, result in enumerate(results, 1):
            context_parts.append(
                f"[文獻 {i} - 相似度: {result['similarity']:.2f}]\n"
                f"來源: {result['metadata']['source']}\n"
                f"頁碼: {result['metadata']['page']}\n"
                f"內容:\n{result['content']}\n"
            )
            
        return "\n---\n".join(context_parts)

def main():
    # 初始化 RAG 系統
    rag = GeminiChromaRAG(api_key="AIzaSyCw2cQTJNLAWCJYPlEvuvKV73Oa3NhZhwo")
    
    # 處理 PDF 文件
    pdf_path = "1512.03385v1.pdf"
    rag.add_pdf(pdf_path)
    
    # 搜索
    query = "檢索resnet的核心概念"
    results = rag.search(query)
    
    # 格式化上下文
    context = rag.format_context(results)
    print("檢索到的相關文獻：")
    print(context)

if __name__ == "__main__":
    main() 