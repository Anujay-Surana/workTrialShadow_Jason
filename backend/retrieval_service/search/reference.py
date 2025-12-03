"""
Reference utilities for parsing and fetching reference data.

This module handles reference ID parsing and fetching full reference
data from the database for emails, schedules, files, and attachments.
"""

import re
from typing import List, Dict, Optional, Tuple
from retrieval_service.data.database import supabase
from retrieval_service.infrastructure.logging import log_debug, log_error


def fetch_full_reference(ref_type: str, ref_id: str) -> Optional[Dict]:
    """
    Fetch complete row data from database for a reference.
    Returns the entire database row as a dictionary.
    
    Args:
        ref_type: Type of reference (email, schedule, file, attachment)
        ref_id: Database ID of the reference
        
    Returns:
        Complete reference data or None if not found
    """
    try:
        if ref_type == 'email':
            resp = supabase.table('emails').select('*').eq('id', ref_id).execute()
            if resp.data and len(resp.data) > 0:
                return {"type": "email", **resp.data[0]}
        
        elif ref_type == 'schedule':
            resp = supabase.table('schedules').select('*').eq('id', ref_id).execute()
            if resp.data and len(resp.data) > 0:
                return {"type": "schedule", **resp.data[0]}
        
        elif ref_type == 'file':
            resp = supabase.table('files').select('*').eq('id', ref_id).execute()
            if resp.data and len(resp.data) > 0:
                return {"type": "file", **resp.data[0]}
        
        elif ref_type == 'attachment':
            resp = supabase.table('attachments').select('*').eq('id', ref_id).execute()
            if resp.data and len(resp.data) > 0:
                return {"type": "attachment", **resp.data[0]}
        
        return None
    
    except Exception as e:
        log_error(f"Error fetching {ref_type} {ref_id}: {e}")
        return None


def parse_reference_ids(llm_output: str) -> Tuple[str, List[str]]:
    """
    Parse REFERENCE_IDS from LLM output.
    
    Args:
        llm_output: Complete LLM response text
        
    Returns:
        Tuple of (content_without_ref_line, list_of_reference_ids)
    """
    content = llm_output
    selected_ids = []
    
    # Extract REFERENCE_IDS line
    ref_match = re.search(r'REFERENCE_IDS:\s*(.+?)(?:\n|$)', llm_output, re.IGNORECASE)
    if ref_match:
        ref_line = ref_match.group(1).strip()
        # Remove the REFERENCE_IDS line from content
        content = re.sub(r'REFERENCE_IDS:.*?(?:\n|$)', '', llm_output, flags=re.IGNORECASE).strip()
        
        if ref_line.lower() != 'none':
            # Parse comma-separated IDs
            selected_ids = [id.strip() for id in ref_line.split(',') if id.strip()]
    
    return content, selected_ids


def fetch_references_by_ids(
    selected_ids: List[str],
    raw_results: List[Dict],
    verbose: bool = False
) -> List[Dict]:
    """
    Fetch full reference data for a list of IDs.
    
    Args:
        selected_ids: List of reference IDs (format: "type_id" or just "id")
        raw_results: Raw search results to lookup types if needed
        verbose: Whether to print debug messages
        
    Returns:
        List of complete reference data dictionaries
    """
    selected_references = []
    
    for ref_id in selected_ids:
        try:
            # Parse type and ID from format like "email_123" or just "123"
            if '_' in ref_id:
                ref_type, ref_db_id = ref_id.split('_', 1)
            else:
                # Try to find in raw_results
                matching = [r for r in raw_results if str(r.get('id')) == ref_id]
                if matching:
                    ref_type = matching[0].get('type')
                    ref_db_id = ref_id
                else:
                    if verbose:
                        log_debug(f"Could not find type for ID: {ref_id}")
                    continue
            
            # Fetch complete row from database
            full_ref = fetch_full_reference(ref_type, ref_db_id)
            if full_ref:
                selected_references.append(full_ref)
            elif verbose:
                log_debug(f"Could not fetch reference: {ref_type}_{ref_db_id}")
        
        except Exception as e:
            if verbose:
                log_error(f"Error fetching reference {ref_id}: {e}")
            continue
    
    return selected_references
