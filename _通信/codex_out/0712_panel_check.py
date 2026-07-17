from html.parser import HTMLParser
from pathlib import Path
p=Path(r'C:\Users\86177\Desktop\智储优控_作战面板.html')
s=p.read_text(encoding='utf-8')
class P(HTMLParser):
    def __init__(self):
        super().__init__(); self.depth=0; self.max_details=0; self.details=0; self.ids=set(); self.dup=[]
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        if tag=='details': self.depth+=1; self.details+=1; self.max_details=max(self.max_details,self.depth)
        if 'id' in d:
            if d['id'] in self.ids:self.dup.append(d['id'])
            self.ids.add(d['id'])
    def handle_endtag(self,tag):
        if tag=='details': self.depth-=1
q=P();q.feed(s);q.close()
assert q.depth==0 and q.max_details<=1 and not q.dup
assert s.count('data-updated=')>=9
assert 'PPT 未重生' in s and '重生PPT' in s
print('HTML_PARSE_OK', 'details=',q.details,'max_details_depth=',q.max_details,'timestamps=',s.count('data-updated='),'bytes=',len(s.encode('utf-8')))
