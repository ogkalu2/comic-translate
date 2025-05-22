import numpy as np
import requests
import json
import time
from typing import List, Dict, Any

from ..utils.textblock import TextBlock
from .base import OCREngine
from app.ui.settings.settings_page import SettingsPage

class MistralOCR(OCREngine):
    """OCR engine using Mistral OCR specific model via REST API with batch processing."""
    def __init__(self):
        self.api_key = None
        self.model = "mistral-ocr-latest"
        self.api_url = "https://api.mistral.ai/v1/ocr"
        self.file_upload_url = "https://api.mistral.ai/v1/files"
        self.batch_job_url = "https://api.mistral.ai/v1/batch/jobs"
        self.file_content_url = "https://api.mistral.ai/v1/files/{file_id}/content"
        self.batch_status_url = "https://api.mistral.ai/v1/batch/jobs/{job_id}"
        self.delete_file_url = "https://api.mistral.ai/v1/files/{file_id}"
        
    def initialize(self, settings: SettingsPage) -> None:
        """
        Initialize the Mistral OCR with API key.
        Args:
            settings: Settings page containing credentials
        """
        credentials = settings.get_credentials(settings.ui.tr('Mistral AI'))
        self.api_key = credentials.get('api_key', '')

    def _upload_batch_file(self, image_urls: List[str]) -> str:
        """Upload a batch file with image URLs to Mistral API."""
        batch = []
        for index, url in enumerate(image_urls):
            entry = {
                "custom_id": str(index),
                "body": {
                    "document": {
                        "type": "image_url",
                        "image_url": url
                    },
                    "include_image_base64": True
                }
            }
            batch.append(json.dumps(entry))
        
        batch_content = "\n".join(batch)
        
        headers = {"Authorization": f"Bearer {self.api_key}"}
        files = {"file": ("batch.jsonl", batch_content, "application/jsonl"), 
                 "purpose": (None, "batch")}
        
        response = requests.post(self.file_upload_url, headers=headers, files=files)
        
        if not response.ok:
            raise Exception(f"Failed to upload batch file: {response.status_code} - {response.text}")
        
        return response.json().get("id")
        
    def _create_batch_job(self, file_id: str) -> str:
        """Create a batch job for OCR processing."""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        payload = {
            "input_files": [file_id],
            "endpoint": "/v1/ocr",
            "model": self.model,
            "metadata": {"comic_ocr": "comic_translate_app"},
            "timeout_hours": 1
        }
        
        response = requests.post(self.batch_job_url, headers=headers, json=payload)
        
        if not response.ok:
            raise Exception(f"Failed to create batch job: {response.status_code} - {response.text}")
        
        return response.json().get("id")
        
    def _check_batch_job_status(self, job_id: str, max_retries: int = 10, retry_delay: int = 2) -> Dict[str, Any]:
        """Check batch job status and wait for completion."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        retries = 0
        while retries < max_retries:
            response = requests.get(self.batch_status_url.format(job_id=job_id), headers=headers)
            
            if not response.ok:
                raise Exception(f"Failed to check batch job status: {response.status_code} - {response.text}")
                
            job_status = response.json()
            status = job_status.get("status", "")
            
            if status == "SUCCESS":
                return job_status
            elif status in ["FAILED", "TIMEOUT_EXCEEDED", "CANCELLED"]:
                # Extract and format error details if available
                error_details = ""
                if job_status.get("errors"):
                    errors = job_status.get("errors", [])
                    error_details = ", ".join([f"{err.get('message')} (count: {err.get('count')})" for err in errors if err.get('message')])
                    error_details = f" Error details: {error_details}"
                raise Exception(f"Batch job failed with status: {status}.{error_details}")
            elif status in ["QUEUED", "RUNNING"]:
                time.sleep(retry_delay)
                retries += 1
            else:
                raise Exception(f"Unknown batch job status: {status}")
                
        raise Exception("Batch job timed out while waiting for completion")
            
    def _get_batch_results(self, output_file_id: str) -> List[Dict[str, Any]]:
        """Get the results of a completed batch job."""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        response = requests.get(self.file_content_url.format(file_id=output_file_id), headers=headers)
        
        if not response.ok:
            raise Exception(f"Failed to get batch results: {response.status_code} - {response.text}")
            
        results = []
        for line in response.text.strip().split('\n'):
            if line:
                results.append(json.loads(line))
                
        return results
        
    def _delete_file(self, file_id: str) -> bool:
        """Delete a file from the Mistral API to clean up resources."""
        if not file_id:
            return False
        
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            response = requests.delete(self.delete_file_url.format(file_id=file_id), headers=headers)
            
            if response.ok:
                return True
            else:
                print(f"Failed to delete file {file_id}: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"Error deleting file {file_id}: {e}")
            return False
            
    def _extract_text_from_result(self, result: Dict[str, Any]) -> str:
        """Extract text from OCR result."""
        if not result.get("response") or result.get("error"):
            return ""
            
        try:
            response_data = result["response"]
            
            if not response_data.get("body") or not response_data["body"].get("pages"):
                return ""
                
            ocr_page = response_data["body"]["pages"][0]
            if not ocr_page.get("markdown"):
                return ""
                
            markdown = ocr_page["markdown"].strip()
            
            # Check if OCR failed and we need to use the base64 image
            if markdown.startswith("![img-") and markdown.endswith(".jpeg)"):
                # OCR failed, attempt to use the base64 image for fallback processing
                if ocr_page.get("images") and len(ocr_page["images"]) > 0:
                    image = ocr_page["images"][0]
                    image_url = image.get("image_base64")
                    if image_url:
                        try:
                            # Use the regular OCR endpoint for fallback processing
                            headers = {
                                "Content-Type": "application/json",
                                "Authorization": f"Bearer {self.api_key}"
                            }
                                
                            payload = {
                                "model": self.model,
                                "document": {
                                    "type": "image_url",
                                    "image_url": image_url
                                }
                            }

                            response = requests.post(self.api_url, headers=headers, json=payload, timeout=30)
                                
                            if response.ok:
                                ocr_result = response.json()
                                if ocr_result.get("pages") and len(ocr_result["pages"]) > 0:
                                    fallback_text = ocr_result["pages"][0].get("markdown", "").strip()
                                    if fallback_text and not fallback_text.startswith("![img-"):
                                        return fallback_text
                        except Exception as e:
                            print(f"Fallback OCR processing failed: {e}")
                
                # If fallback failed or wasn't possible, return empty string
                return ""
                    
            return markdown
            
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            print(f"Error extracting text from OCR result: {e}")
            return ""

    def process_image(self, img: np.ndarray, blk_list: list[TextBlock]) -> list[TextBlock]:
        """
        Process an image with Mistral-based OCR using the batch API.
        Args:
            img: Input image as numpy array
            blk_list: List of TextBlock objects to update with OCR text

        Returns:
            List of updated TextBlock objects with recognized text
        """
        if not blk_list:
            return blk_list
            
        # Filter blocks with valid coordinates
        valid_blocks = []
        image_urls = []
        
        for i, blk in enumerate(blk_list):
            if blk.xyxy is None:
                blk.text = ""
                continue
                
            x1, y1, x2, y2 = blk.xyxy.astype(int)
            h, w = img.shape[:2]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            
            if x1 >= x2 or y1 >= y2 or (x2-x1)*(y2-y1) == 0:
                blk.text = ""
                continue
                
            cropped_img = img[y1:y2, x1:x2]
            
            if cropped_img.size == 0:
                blk.text = ""
                continue
                
            encoded_img = self.encode_image(cropped_img, ext='.jpg')
            image_url = f"data:image/jpeg;base64,{encoded_img}"
            
            image_urls.append(image_url)
            valid_blocks.append(blk)
            
        if not valid_blocks:
            return blk_list
            
        input_file_id = None
        output_file_id = None
        error_file_id = None
        
        try:
            # Process batch OCR request
            input_file_id = self._upload_batch_file(image_urls)
            job_id = self._create_batch_job(input_file_id)
            job_status = self._check_batch_job_status(job_id)
            
            output_file_id = job_status.get("output_file")
            error_file_id = job_status.get("error_file")
            
            if output_file_id:
                results = self._get_batch_results(output_file_id)
                
                # Map results back to text blocks
                if len(results) == len(valid_blocks):
                    for i, (result, blk) in enumerate(zip(results, valid_blocks)):
                        blk.text = self._extract_text_from_result(result)
                else:
                    print(f"Mismatch between results count ({len(results)}) and blocks count ({len(valid_blocks)})")
            else:
                print("No output file in job status response")
                
        except Exception as e:
            print(f"Error in batch OCR processing: {e}")
        finally:
            # Clean up files regardless of success or failure
            if input_file_id:
                self._delete_file(input_file_id)
            if output_file_id:
                self._delete_file(output_file_id)
            if error_file_id:
                self._delete_file(error_file_id)
            
        return blk_list
