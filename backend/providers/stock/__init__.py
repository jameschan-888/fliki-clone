import os
from pathlib import Path

import httpx

from providers.base import ProviderError, StockProvider


def download(client, url, destination):
    destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
    with client.stream("GET",url,follow_redirects=True) as response:
        response.raise_for_status()
        with destination.open("wb") as output:
            for chunk in response.iter_bytes(): output.write(chunk)
    if destination.stat().st_size < 1024: raise ProviderError("Downloaded stock asset is empty")


class PexelsProvider(StockProvider):
    name="pexels"
    def __init__(self,api_key=None): self.api_key=api_key or os.getenv("PEXELS_API_KEY","")
    def fetch(self,query,destination):
        if not self.api_key: raise ProviderError("PEXELS_API_KEY is missing")
        with httpx.Client(timeout=30,headers={"Authorization":self.api_key}) as client:
            response=client.get("https://api.pexels.com/videos/search",params={"query":query,"per_page":5,"orientation":"landscape"});response.raise_for_status()
            videos=response.json().get("videos",[])
            if not videos: raise ProviderError(f"Pexels returned no videos for {query}")
            files=[item for item in videos[0].get("video_files",[]) if item.get("file_type")=="video/mp4"]
            if not files: raise ProviderError("Pexels video has no MP4 file")
            selected=min(files,key=lambda item: abs((item.get("width") or 1280)-1280))
            download(client,selected["link"],destination)
            return {"provider":self.name,"source_url":selected["link"],"page_url":videos[0].get("url"),"creator":videos[0].get("user",{}).get("name"),"local_path":str(destination)}


class PixabayProvider(StockProvider):
    name="pixabay"
    def __init__(self,api_key=None): self.api_key=api_key or os.getenv("PIXABAY_API_KEY","")
    def fetch(self,query,destination):
        if not self.api_key: raise ProviderError("PIXABAY_API_KEY is missing")
        with httpx.Client(timeout=30) as client:
            response=client.get("https://pixabay.com/api/videos/",params={"key":self.api_key,"q":query,"per_page":5,"safesearch":"true"});response.raise_for_status()
            hits=response.json().get("hits",[])
            if not hits: raise ProviderError(f"Pixabay returned no videos for {query}")
            variants=hits[0].get("videos",{})
            selected=variants.get("medium") or variants.get("small") or variants.get("large") or variants.get("tiny")
            if not selected: raise ProviderError("Pixabay video has no downloadable variant")
            download(client,selected["url"],destination)
            return {"provider":self.name,"source_url":selected["url"],"page_url":hits[0].get("pageURL"),"creator":hits[0].get("user"),"local_path":str(destination)}


def fetch_with_fallback(query,destination):
    errors=[]
    for provider in (PexelsProvider(),PixabayProvider()):
        try:return provider.fetch(query,destination)
        except Exception as error: errors.append(f"{provider.name}: {error}")
    raise ProviderError("; ".join(errors))
