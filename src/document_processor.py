"""
Medical Document Intelligence Processor

Extracts structured clinical information from medical documents
using Azure AI Document Intelligence.

Features:
- Multi-format support (PDF, DOCX, images, text)
- Structured extraction (diagnoses, medications, vital signs)
- Healthcare-specific parsing
- Error handling and validation
"""

import os
from typing import Dict, List, Optional
from azure.core.credentials import AzureKeyCredential
from azure.ai.formrecognizer import DocumentAnalysisClient
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


class MedicalDocumentProcessor:
    """
    Production-grade medical document processor with Azure AI integration.
    
    Capabilities:
    - Extract clinical text from various formats
    - Parse structured medical data
    - Handle healthcare documents (lab reports, clinical notes, guidelines)
    - Robust error handling
    """
    
    def __init__(self):
        """Initialize Azure Document Intelligence client"""
        self.endpoint = os.getenv("DOCUMENT_INTELLIGENCE_ENDPOINT")
        self.key = os.getenv("DOCUMENT_INTELLIGENCE_KEY")
        
        if not self.endpoint or not self.key:
            raise ValueError(
                "Missing Document Intelligence credentials. "
                "Please configure DOCUMENT_INTELLIGENCE_ENDPOINT and DOCUMENT_INTELLIGENCE_KEY in .env"
            )
        
        self.client = DocumentAnalysisClient(
            endpoint=self.endpoint,
            credential=AzureKeyCredential(self.key)
        )
        
        logger.info("Document Intelligence client initialized")
    
    def analyze_document(self, file_path: str) -> Dict:
        """
        Analyze medical document and extract structured information.
        
        Args:
            file_path: Path to document file
            
        Returns:
            Dictionary containing:
            - content: Full text content
            - key_value_pairs: Extracted key-value data
            - tables: Extracted tables (if any)
            - metadata: Document metadata
        
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format unsupported
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Document not found: {file_path}")
        
        # Determine file type
        file_ext = os.path.splitext(file_path)[1].lower()
        
        if file_ext == '.txt':
            return self._analyze_text_file(file_path)
        elif file_ext in ['.pdf', '.jpg', '.jpeg', '.png', '.docx']:
            return self._analyze_with_azure(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_ext}")
    
    def _analyze_text_file(self, file_path: str) -> Dict:
        """Process plain text medical documents"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            logger.info(f"Analyzed text file: {file_path} ({len(content)} chars)")
            
            return {
                "content": content,
                "key_value_pairs": {},
                "tables": [],
                "metadata": {
                    "file_path": file_path,
                    "format": "text",
                    "pages": 1,
                    "characters": len(content)
                }
            }
        except Exception as e:
            logger.error(f"Error analyzing text file: {e}")
            raise
    
    def _analyze_with_azure(self, file_path: str) -> Dict:
        """Process document using Azure Document Intelligence"""
        try:
            with open(file_path, "rb") as f:
                poller = self.client.begin_analyze_document(
                    "prebuilt-document",
                    document=f
                )
            
            result = poller.result()
            
            # Extract full text content
            content = self._extract_text(result)
            
            # Extract key-value pairs
            key_values = self._extract_key_values(result)
            
            # Extract tables
            tables = self._extract_tables(result)
            
            logger.info(
                f"Analyzed document: {file_path} "
                f"({len(result.pages)} pages, {len(content)} chars)"
            )
            
            return {
                "content": content,
                "key_value_pairs": key_values,
                "tables": tables,
                "metadata": {
                    "file_path": file_path,
                    "format": os.path.splitext(file_path)[1],
                    "pages": len(result.pages),
                    "characters": len(content)
                }
            }
        except Exception as e:
            logger.error(f"Error analyzing document with Azure: {e}")
            raise
    
    def _extract_text(self, result) -> str:
        """Extract all text content from document"""
        content = ""
        for page in result.pages:
            for line in page.lines:
                content += line.content + "\n"
        return content.strip()
    
    def _extract_key_values(self, result) -> Dict[str, str]:
        """Extract key-value pairs (e.g., Patient Name: John Doe)"""
        key_values = {}
        if result.key_value_pairs:
            for kv in result.key_value_pairs:
                if kv.key and kv.value:
                    key = kv.key.content.strip()
                    value = kv.value.content.strip()
                    key_values[key] = value
        return key_values
    
    def _extract_tables(self, result) -> List[List[List[str]]]:
        """Extract tables from document"""
        tables_data = []
        if result.tables:
            for table in result.tables:
                table_data = []
                for cell in table.cells:
                    # Group by row
                    while len(table_data) <= cell.row_index:
                        table_data.append([])
                    while len(table_data[cell.row_index]) <= cell.column_index:
                        table_data[cell.row_index].append("")
                    table_data[cell.row_index][cell.column_index] = cell.content
                tables_data.append(table_data)
        return tables_data
    
    def batch_analyze(self, file_paths: List[str]) -> List[Dict]:
        """
        Analyze multiple documents in batch.
        
        Args:
            file_paths: List of document paths
            
        Returns:
            List of analysis results
        """
        results = []
        for file_path in file_paths:
            try:
                result = self.analyze_document(file_path)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to analyze {file_path}: {e}")
                results.append({
                    "error": str(e),
                    "file_path": file_path
                })
        
        logger.info(f"Batch analyzed {len(results)} documents")
        return results


# Demo / Testing
if __name__ == "__main__":
    print("="*70)
    print("MEDICAL DOCUMENT INTELLIGENCE PROCESSOR")
    print("="*70)
    
    processor = MedicalDocumentProcessor()
    
    # Test with sample guideline
    test_file = "data/medical_guidelines/diabetes_guideline.txt"
    
    if os.path.exists(test_file):
        print(f"\nAnalyzing: {test_file}")
        result = processor.analyze_document(test_file)
        
        print(f"\nAnalysis complete!")
        print(f"   Format: {result['metadata']['format']}")
        print(f"   Pages: {result['metadata']['pages']}")
        print(f"   Characters: {result['metadata']['characters']}")
        print(f"   Key-value pairs: {len(result['key_value_pairs'])}")
        print(f"   Tables: {len(result['tables'])}")
        
        print(f"\nContent preview (first 300 chars):")
        print("-" * 70)
        print(result['content'][:300] + "...")
    else:
        print(f"\nWarning: Test file not found: {test_file}")
        print("Please create sample medical guidelines in data/medical_guidelines/")