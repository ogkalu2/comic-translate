import math
import numpy as np
from typing import Callable, Any
from .general import calculate_iou


class ImageSlicer:
    """
    Utility class to handle slicing extremely tall images (Webtoons) for object detection and recombining results.
    """
    
    def __init__(self, 
                 height_to_width_ratio_threshold: float = 3.5,
                 target_slice_ratio: float = 3.0,
                 overlap_height_ratio: float = 0.2,
                 min_slice_height_ratio: float = 0.7,
                 merge_iou_threshold: float = 0.2,
                 duplicate_iou_threshold: float = 0.5,
                 merge_y_distance_threshold: float = 0.1,
                 containment_threshold: float = 0.85):  
        """
        Initialize the image slicer with configuration parameters.
        
        Args:
            height_to_width_ratio_threshold: Aspect ratio threshold to trigger slicing
            target_slice_ratio: Desired height/width ratio for each slice
            overlap_height_ratio: Overlap ratio between vertical slices
            min_slice_height_ratio: Minimum ratio of last slice height to target height
                                   before merging with previous slice
            merge_iou_threshold: IoU threshold for merging boxes across slices
            duplicate_iou_threshold: IoU threshold for identifying duplicate detections
            merge_y_distance_threshold: Maximum distance (relative to image height) 
                                      between boxes to be considered for merging
            containment_threshold: Threshold for determining if one box is contained within another
        """
        self.height_to_width_ratio_threshold = height_to_width_ratio_threshold
        self.target_slice_ratio = target_slice_ratio
        self.overlap_height_ratio = overlap_height_ratio
        self.min_slice_height_ratio = min_slice_height_ratio
        self.merge_iou_threshold = merge_iou_threshold
        self.duplicate_iou_threshold = duplicate_iou_threshold
        self.merge_y_distance_threshold = merge_y_distance_threshold
        self.containment_threshold = containment_threshold
        
    def should_slice(self, image: np.ndarray) -> bool:
        height, width = image.shape[:2]
        aspect_ratio = height / width
        return aspect_ratio > self.height_to_width_ratio_threshold
    
    def calculate_slice_params(self, image: np.ndarray) -> tuple[int, int, int, int]:
        height, width = image.shape[:2]
        
        slice_width = width  # Full width of the image
        slice_height = int(slice_width * self.target_slice_ratio)
        effective_slice_height = int(slice_height * (1 - self.overlap_height_ratio))
        
        # Calculate the number of slices needed
        num_slices = math.ceil(height / effective_slice_height)
        
        # Check if the last slice would be too small
        last_slice_start = (num_slices - 1) * effective_slice_height
        last_slice_height = height - last_slice_start
        last_slice_height_ratio = last_slice_height / slice_height
        
        # If the last slice is too small, merge with previous slice
        if last_slice_height_ratio < self.min_slice_height_ratio and num_slices > 1:
            num_slices -= 1
            
        return slice_width, slice_height, effective_slice_height, num_slices
    
    def get_slice(self, image: np.ndarray, slice_number: int, 
                 effective_slice_height: int, slice_height: int) -> tuple[np.ndarray, int, int]:
        """
        Extract a slice from the image.
        
        Args:
            image: Input image as numpy array
            slice_number: Index of the slice to extract
            effective_slice_height: Height of slice minus overlap
            slice_height: Total height of a slice including overlap
            
        Returns:
            Tuple of (slice image, start_y, end_y)
        """
        height, width = image.shape[:2]
        
        # Calculate the starting y-coordinate for this slice
        start_y = slice_number * effective_slice_height
        
        # For the last slice, make sure we go to the end of the image
        if slice_number == math.ceil(height / effective_slice_height) - 1:
            end_y = height
        else:
            end_y = min(start_y + slice_height, height)
        
        # Extract the slice
        slice_image = image[start_y:end_y, 0:width].copy()
        
        return slice_image, start_y, end_y
    
    def adjust_box_coordinates(self, boxes: np.ndarray, start_y: int) -> np.ndarray:
        """
        Adjust box coordinates to match original image.
        
        Args:
            boxes: Array of boxes in format [x1, y1, x2, y2]
            start_y: Y-coordinate offset for this slice
            
        Returns:
            Adjusted boxes
        """
        if boxes.size == 0:
            return boxes
            
        adjusted_boxes = boxes.copy()
        adjusted_boxes[:, 1] += start_y  # y1
        adjusted_boxes[:, 3] += start_y  # y2
        return adjusted_boxes
    
    def box_contained(self, box1: list[float], box2: list[float]) -> tuple[bool, float, int]:
        """
        Check if one box is contained within another box.
        
        Args:
            box1, box2: Boxes in format [x1, y1, x2, y2]
            
        Returns:
            Tuple of (is_contained, containment_ratio, which_contains)
                is_contained: True if one box is contained within the other
                containment_ratio: Area ratio of intersection to smaller box
                which_contains: 1 if box1 contains box2, 2 if box2 contains box1, 0 otherwise
        """
        # Calculate box areas
        area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
        area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
        
        # Calculate intersection
        intersection_x1 = max(box1[0], box2[0])
        intersection_y1 = max(box1[1], box2[1])
        intersection_x2 = min(box1[2], box2[2])
        intersection_y2 = min(box1[3], box2[3])
        
        if intersection_x2 <= intersection_x1 or intersection_y2 <= intersection_y1:
            return False, 0, 0
            
        intersection_area = (intersection_x2 - intersection_x1) * (intersection_y2 - intersection_y1)
        
        # Check containment
        smaller_area = min(area1, area2)
        containment_ratio = intersection_area / smaller_area
        
        if containment_ratio >= self.containment_threshold:
            if area1 > area2:  # box1 contains box2
                return True, containment_ratio, 1
            else:  # box2 contains box1
                return True, containment_ratio, 2
        
        return False, containment_ratio, 0
    
    def merge_overlapping_boxes(self, boxes: np.ndarray, class_ids: np.ndarray = None, 
                               image_height: int = 1) -> tuple[np.ndarray, np.ndarray]:
        """
        Merge boxes that are likely part of the same object across slices and
        remove duplicate detections from overlapping slices.
        
        Args:
            boxes: Array of boxes in format [x1, y1, x2, y2]
            class_ids: Array of class IDs corresponding to each box
            image_height: Height of the original image (for scaling distance threshold)
            
        Returns:
            Tuple of (merged_boxes, merged_class_ids)
        """
        if boxes.size == 0:
            return boxes, np.array([]) if class_ids is not None else boxes
            
        # Convert to list for easier manipulation
        box_list = boxes.tolist()
        class_list = class_ids.tolist() if class_ids is not None else [0] * len(box_list)
        
        # Calculate distance threshold in pixels
        y_distance_threshold = self.merge_y_distance_threshold * image_height
        
        i = 0
        while i < len(box_list) - 1:
            j = i + 1
            while j < len(box_list):
                # Only merge boxes with same class ID if class_ids is provided
                if class_ids is not None and class_list[i] != class_list[j]:
                    j += 1
                    continue
                    
                box1 = box_list[i]
                box2 = box_list[j]
                
                # Calculate IoU to identify duplicates or highly overlapping boxes
                iou = calculate_iou(box1, box2)
                
                # Calculate box dimensions
                box1_width = box1[2] - box1[0]
                box1_height = box1[3] - box1[1]
                box2_width = box2[2] - box2[0]
                box2_height = box2[3] - box2[1]
                box1_area = box1_width * box1_height
                box2_area = box2_width * box2_height
                
                # Check for containment (one box mostly inside another)
                is_contained, containment_ratio, which_contains = self.box_contained(box1, box2)
                
                # Case 1: One box is mostly contained within the other
                if is_contained:
                    # Keep the larger box
                    if which_contains == 1:  # box1 contains box2
                        # Remove box2
                        box_list.pop(j)
                        if class_ids is not None:
                            class_list.pop(j)
                    else:  # box2 contains box1
                        # Replace box1 with box2 and remove box2
                        box_list[i] = box2
                        box_list.pop(j)
                        if class_ids is not None:
                            class_list.pop(j)
                    continue
                
                # Case 2: High IoU - likely the same object detected twice (duplicate)
                if iou >= self.duplicate_iou_threshold:
                    # Choose the larger box (which often has better coverage of the object)
                    if box2_area > box1_area:
                        box_list[i] = box2  # Keep the larger box
                    
                    # Remove the duplicate
                    box_list.pop(j)
                    if class_ids is not None:
                        class_list.pop(j)
                    continue
                
                # Calculate vertical distance between boxes
                y_dist = min(abs(box1[1] - box2[3]), abs(box1[3] - box2[1]))
                
                # Calculate horizontal overlap
                x_overlap = max(0, min(box1[2], box2[2]) - max(box1[0], box2[0]))
                x_overlap_ratio = x_overlap / min(box1_width, box2_width) if min(box1_width, box2_width) > 0 else 0
                
                # Calculate size ratio to prevent merging very different sized boxes
                size_ratio = min(box1_area, box2_area) / max(box1_area, box2_area) if max(box1_area, box2_area) > 0 else 0
                
                # Case 3: Boxes likely part of the same object across slices
                # More strict conditions to prevent over-merging
                if (y_dist < y_distance_threshold and  # Close vertically
                    x_overlap_ratio > self.merge_iou_threshold and  # Sufficient horizontal overlap
                    size_ratio > 0.3 and  # Similar size (prevent merging very different sized boxes)
                    # Check that boxes are not too far apart horizontally
                    abs(box1[0] - box2[0]) < 0.5 * max(box1_width, box2_width) and
                    abs(box1[2] - box2[2]) < 0.5 * max(box1_width, box2_width)):
                    
                    # Merge the boxes
                    merged_box = [
                        min(box1[0], box2[0]),
                        min(box1[1], box2[1]),
                        max(box1[2], box2[2]),
                        max(box1[3], box2[3])
                    ]
                    
                    # Additional check: Don't allow merged boxes to get too large
                    merged_width = merged_box[2] - merged_box[0]
                    merged_height = merged_box[3] - merged_box[1]
                    merged_area = merged_width * merged_height
                    
                    # If merged box is more than 3x larger than either original box, don't merge
                    if merged_area > 3 * max(box1_area, box2_area):
                        j += 1
                        continue
                        
                    box_list[i] = merged_box
                    box_list.pop(j)
                    if class_ids is not None:
                        class_list.pop(j)
                else:
                    j += 1
            i += 1
            
        merged_boxes = np.array(box_list)
        merged_class_ids = np.array(class_list) if class_ids is not None else None
        
        return merged_boxes, merged_class_ids
    
    def process_slices_for_detection(self, 
                                    image: np.ndarray, 
                                    detect_func: Callable) -> Any:
        """
        Process an image by slicing it and running detection on each slice.
        Flexible implementation that adapts to the return type of the detect_func.
        
        Args:
            image: Input image as numpy array
            detect_func: Function that performs detection on a slice
                        Can return different types based on detector implementation
            
        Returns:
            Detection results combined from all slices, matching the return type of detect_func
        """
        if not self.should_slice(image):
            # If image doesn't need slicing, process it directly
            return detect_func(image)
            
        # Calculate slicing parameters
        slice_width, slice_height, effective_slice_height, num_slices = self.calculate_slice_params(image)
        
        # First, let's determine the return type by calling the function on the first slice
        slice_img, start_y, _ = self.get_slice(
            image, 0, effective_slice_height, slice_height
        )
        first_result = detect_func(slice_img)
        
        # Check return type to determine how to process the results
        if isinstance(first_result, tuple) and len(first_result) == 2:
            # Case 1: Function returns a tuple of two arrays (bubble_boxes, text_boxes)
            return self._process_box_tuple_results(image, detect_func, effective_slice_height)
        elif isinstance(first_result, np.ndarray):
            # Case 2: Function returns a single array of boxes
            return self._process_single_box_array_results(image, detect_func, effective_slice_height)
        else:
            # For any other return type, we'll need to handle it specifically
            # This is just a placeholder for custom implementations
            raise NotImplementedError(
                "Detector return type not supported. Please implement custom slicing logic."
            )
    
    def _process_box_tuple_results(self, 
                                  image: np.ndarray,
                                  detect_func: Callable[[np.ndarray], tuple[np.ndarray, np.ndarray]],
                                  effective_slice_height: int) -> tuple[np.ndarray, np.ndarray]:
        """
        Process slices for detectors that return a tuple of (bubble_boxes, text_boxes).
        
        Args:
            image: Input image
            detect_func: Detection function
            effective_slice_height: Height of slice minus overlap
            
        Returns:
            Tuple of (combined_bubble_boxes, combined_text_boxes)
        """
        height, width = image.shape[:2]
        num_slices = math.ceil(height / effective_slice_height)
        slice_height = int(width * self.target_slice_ratio)
        
        all_bubble_boxes = []
        all_text_boxes = []
        
        for slice_number in range(num_slices):
            slice_img, start_y, _ = self.get_slice(
                image, slice_number, effective_slice_height, slice_height
            )
            
            # Run detection on this slice
            bubble_boxes, text_boxes = detect_func(slice_img)
            
            # Adjust coordinates to match original image
            if isinstance(bubble_boxes, np.ndarray) and bubble_boxes.size > 0:
                bubble_boxes = self.adjust_box_coordinates(bubble_boxes, start_y)
                all_bubble_boxes.append(bubble_boxes)
                
            if isinstance(text_boxes, np.ndarray) and text_boxes.size > 0:
                text_boxes = self.adjust_box_coordinates(text_boxes, start_y)
                all_text_boxes.append(text_boxes)
        
        # Combine all detections
        combined_bubble_boxes = np.vstack(all_bubble_boxes) if all_bubble_boxes else np.array([])
        combined_text_boxes = np.vstack(all_text_boxes) if all_text_boxes else np.array([])
        
        # Merge overlapping boxes and remove duplicates
        if combined_bubble_boxes.size > 0:
            combined_bubble_boxes, _ = self.merge_overlapping_boxes(
                combined_bubble_boxes, 
                image_height=image.shape[0]
            )
            
        if combined_text_boxes.size > 0:
            combined_text_boxes, _ = self.merge_overlapping_boxes(
                combined_text_boxes,
                image_height=image.shape[0]
            )
            
        return combined_bubble_boxes, combined_text_boxes
    
    def _process_single_box_array_results(self, 
                                          image: np.ndarray, 
                                          detect_func: Callable[[np.ndarray], np.ndarray],
                                          effective_slice_height: int) -> np.ndarray:
        """
        Process slices for detectors that return a single array of boxes.
        
        Args:
            image: Input image
            detect_func: Detection function
            effective_slice_height: Height of slice minus overlap
            
        Returns:
            Combined array of boxes
        """
        height, width = image.shape[:2]
        num_slices = math.ceil(height / effective_slice_height)
        slice_height = int(width * self.target_slice_ratio)
        
        all_boxes = []
        
        for slice_number in range(num_slices):
            slice_img, start_y, _ = self.get_slice(
                image, slice_number, effective_slice_height, slice_height
            )
            
            # Run detection on this slice
            boxes = detect_func(slice_img)
            
            # Adjust coordinates to match original image
            if isinstance(boxes, np.ndarray) and boxes.size > 0:
                boxes = self.adjust_box_coordinates(boxes, start_y)
                all_boxes.append(boxes)
        
        # Combine all detections
        combined_boxes = np.vstack(all_boxes) if all_boxes else np.array([])
        
        # Merge overlapping boxes and remove duplicates
        if combined_boxes.size > 0:
            combined_boxes, _ = self.merge_overlapping_boxes(
                combined_boxes, 
                image_height=image.shape[0]
            )
            
        return combined_boxes