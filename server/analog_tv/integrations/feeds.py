import hashlib, re, xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import httpx

class RssNewsProvider:
    async def headlines(self,url,limit=5):
        async with httpx.AsyncClient(timeout=20,follow_redirects=True) as c: r=await c.get(url); r.raise_for_status()
        root=ET.fromstring(r.content); out=[]
        for item in root.findall('.//item'):
            title=(item.findtext('title') or '').strip()
            if title and title not in out: out.append(title)
            if len(out)>=limit:break
        return out

class EmyWarningProvider:
    @staticmethod
    def _region_terms(region):
        value=(region or '').strip().lower()
        if not value:return []
        aliases={
            'attica':['attica','athens','αττική','αττικη','αθήνα','αθηνα'],
            'athens':['attica','athens','αττική','αττικη','αθήνα','αθηνα'],
            'αττική':['attica','athens','αττική','αττικη','αθήνα','αθηνα'],
            'αθηνα':['attica','athens','αττική','αττικη','αθήνα','αθηνα'],
        }
        return aliases.get(value,[value])

    @classmethod
    def _matches_region(cls,text,region):
        terms=cls._region_terms(region)
        if not terms:return True
        haystack=(text or '').lower()
        return any(term in haystack for term in terms)

    async def warning(self,url,region=None):
        async with httpx.AsyncClient(timeout=20,follow_redirects=True,headers={'User-Agent':'Analog-TV/2.1.0'}) as c:
            r=await c.get(url); r.raise_for_status()
        content_type=r.headers.get('content-type','').lower()
        if 'atom' in content_type or '<feed' in r.text[:500].lower():
            root=ET.fromstring(r.content)
            ns={'a':'http://www.w3.org/2005/Atom'}
            entries=root.findall('a:entry',ns)
            if not entries:return None
            parts=[]
            for entry in entries:
                title=(entry.findtext('a:title',default='',namespaces=ns) or '').strip()
                summary=(entry.findtext('a:summary',default='',namespaces=ns) or '').strip()
                content=(entry.findtext('a:content',default='',namespaces=ns) or '').strip()
                text=re.sub(r'<[^>]+>',' ', ' '.join([summary,content]))
                text=re.sub(r'\s+',' ',text).strip()
                phrase=' — '.join(x for x in [title,text] if x)
                if phrase and self._matches_region(phrase,region):parts.append(phrase[:350])
                if len(parts)>=6:break
            if not parts:return None
            snippet='  •  '.join(parts)[:1600]
            return {'text':snippet,'hash':hashlib.sha256(snippet.encode('utf-8')).hexdigest()}
        soup=BeautifulSoup(r.text,'html.parser')
        text=' '.join(soup.stripped_strings)
        if 'Δεν υπάρχει έκτακτο δελτίο' in text:return None
        markers=['ΕΚΤΑΚΤΟ ΔΕΛΤΙΟ','Κόκκινη προειδοποίηση','Πορτοκαλί προειδοποίηση','Κίτρινη προειδοποίηση']
        idx=min([text.find(m) for m in markers if text.find(m)>=0] or [0])
        snippet=re.sub(r'\s+',' ',text[idx:idx+900]).strip()
        if not snippet or not self._matches_region(snippet,region):return None
        return {'text':snippet,'hash':hashlib.sha256(snippet.encode('utf-8')).hexdigest()}
