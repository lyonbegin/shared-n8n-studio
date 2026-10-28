import http from 'node:http';
import {readFile, stat} from 'node:fs/promises';
import {extname, resolve, sep} from 'node:path';
const root=resolve('./dist');
const mime={'.html':'text/html; charset=utf-8','.js':'application/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.svg':'image/svg+xml','.png':'image/png','.json':'application/json; charset=utf-8','.ico':'image/x-icon'};
const server=http.createServer(async(req,res)=>{
  const url=new URL(req.url||'/', 'http://localhost');
  if(url.pathname==='/health'){res.writeHead(200,{'Content-Type':'text/plain'});return res.end('ok');}
  if(req.method!=='GET' && req.method!=='HEAD'){res.writeHead(405);return res.end();}
  const pathname=decodeURIComponent(url.pathname);
  const candidate=resolve(root,'.'+pathname);
  if(candidate!==root&&!candidate.startsWith(root+sep)){res.writeHead(403);return res.end();}
  let file=candidate;
  try{if(!(await stat(file)).isFile())file=resolve(root,'index.html');}
  catch{file=resolve(root,'index.html');}
  try{const bytes=await readFile(file);res.writeHead(200,{
    'Content-Type':mime[extname(file)]||'application/octet-stream',
    'Cache-Control':file.endsWith('index.html')?'no-store':'public, max-age=300',
    'X-Content-Type-Options':'nosniff',
    'Referrer-Policy':'no-referrer',
    'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
  });res.end(req.method==='HEAD'?undefined:bytes);}
  catch(e){res.writeHead(500);res.end('Server error');}
});
server.listen(Number(process.env.PORT||3000),'0.0.0.0');
