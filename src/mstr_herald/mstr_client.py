import requests
from typing import Dict, Optional, Any
from services.settings import get_settings
import logging

logger = logging.getLogger(__name__)


class MstrClient:
    """Low-level MicroStrategy REST API client."""
    
    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.MSTR_URL_API
        self.username = self.settings.MSTR_USERNAME
        self.password = self.settings.MSTR_PASSWORD
        self.project = self.settings.MSTR_PROJECT
        self._auth_token: Optional[str] = None
        self._session = requests.Session()
    
    def ensure_authenticated(self) -> str:
        """Ensure we have a valid auth token, login if needed."""
        if self._auth_token:
            return self._auth_token
        
        logger.info("Authenticating with MicroStrategy...")
        
        response = self._session.post(
            f"{self.base_url}/auth/login",
            json={
                "username": self.username,
                "password": self.password,
                "loginMode": 1
            },
            timeout=30
        )
        response.raise_for_status()
        
        self._auth_token = response.headers.get('X-MSTR-AuthToken')
        if not self._auth_token:
            raise ValueError("No auth token received from MicroStrategy")
        
        logger.info("Successfully authenticated with MicroStrategy")
        return self._auth_token
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with auth token."""
        token = self.ensure_authenticated()
        return {
            'X-MSTR-AuthToken': token,
            'X-MSTR-ProjectID': self.project,
            'Content-Type': 'application/json'
        }
    
    def get_report_data(
        self,
        dossier_id: str,
        viz_key: str,
        view_filter: Optional[Dict[str, Any]] = None,
        limit: int = 0,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Fetch data from a dossier visualization.
        
        Args:
            dossier_id: Dossier ID
            viz_key: Visualization key
            view_filter: Optional filter payload
            limit: Number of rows (0 = all)
            offset: Offset for pagination
        
        Returns:
            MSTR API response with grid data
        """
        # Create dossier instance with filters
        instance_url = f"{self.base_url}/dossiers/{dossier_id}/instances"
        logger.debug(f"Creating MSTR instance: {instance_url}")
        
        # Build instance payload with filters
        instance_payload: Dict[str, Any] = {}
        if view_filter:
            instance_payload["viewFilter"] = view_filter
        
        instance_response = self._session.post(
            instance_url,
            headers=self._get_headers(),
            json=instance_payload,
            timeout=60
        )
        
        if not instance_response.ok:
            logger.error(f"MSTR instance creation failed: {instance_response.status_code} - {instance_response.text}")
        
        instance_response.raise_for_status()
        instance_id = instance_response.json()['mid']
        
        # Build request payload
        payload: Dict[str, Any] = {
            "requestedObjects": {
                "visualizations": [{"id": viz_key}]
            }
        }
        
        if view_filter:
            payload["viewFilter"] = view_filter
        
        if limit > 0:
            payload["limit"] = limit
        if offset > 0:
            payload["offset"] = offset
        
        # Fetch visualization data as CSV (this is what v1 uses!)
        csv_url = f"{self.base_url}/documents/{dossier_id}/instances/{instance_id}/visualizations/{viz_key}/csv"
        logger.debug(f"Fetching CSV from: {csv_url}")
        
        data_response = self._session.post(
            csv_url,
            headers=self._get_headers(),
            timeout=300
        )
        
        if not data_response.ok:
            logger.error(f"MSTR CSV fetch failed: {data_response.status_code} - {data_response.text}")
        
        data_response.raise_for_status()

        return data_response
    
    def get_dossier_definition(self, dossier_id: str) -> Dict[str, Any]:
        """
        Get dossier metadata (for auto-discovery).
        
        Returns:
            Dossier definition with chapters, visualizations, filters
        """
        response = self._session.get(
            f"{self.base_url}/dossiers/{dossier_id}/definition",
            headers=self._get_headers(),
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    
    def logout(self):
        """Logout and clear auth token."""
        if self._auth_token:
            try:
                self._session.post(
                    f"{self.base_url}/auth/logout",
                    headers={'X-MSTR-AuthToken': self._auth_token},
                    timeout=10
                )
            except:
                pass
            finally:
                self._auth_token = None


# Singleton instance
_mstr_client: Optional[MstrClient] = None


def get_mstr_client() -> MstrClient:
    """Get MSTR client singleton."""
    global _mstr_client
    if _mstr_client is None:
        _mstr_client = MstrClient()
    return _mstr_client
