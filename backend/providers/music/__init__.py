import os
from pathlib import Path

import httpx

from providers.base import ProviderError,MusicProvider


class FreesoundProvider(MusicProvider):
    name="freesound"
    def __init__(self,api_key=None): self.api_key=api_key or os.getenv("FREESOUND_API_KEY","")
    def fetch(self,query,destination):
        if not self.api_key: raise ProviderError("FREESOUND_API_KEY is missing")
        destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
        params={"query":query,"token":self.api_key,"fields":"id,name,username,license,previews,url,duration","page_size":10,"filter":"duration:[20 TO 300]"}
        with httpx.Client(timeout=30) as client:
            response=client.get("https://freesound.org/apiv2/search/text/",params=params);response.raise_for_status()
            results=response.json().get("results",[])
            if not results: raise ProviderError(f"Freesound returned no audio for {query}")
            selected=results[0];url=selected.get("previews",{}).get("preview-hq-mp3") or selected.get("previews",{}).get("preview-lq-mp3")
            if not url: raise ProviderError("Freesound result has no MP3 preview")
            with client.stream("GET",url,follow_redirects=True) as stream:
                stream.raise_for_status()
                with destination.open("wb") as output:
                    for chunk in stream.iter_bytes(): output.write(chunk)
        return {"provider":self.name,"source_url":url,"page_url":selected.get("url"),"creator":selected.get("username"),"license":selected.get("license"),"duration_seconds":selected.get("duration"),"local_path":str(destination)}
