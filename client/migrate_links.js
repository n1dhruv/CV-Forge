const fs = require('fs');
const path = require('path');

const walk = (dir) => {
  let results = [];
  const list = fs.readdirSync(dir);
  list.forEach((file) => {
    file = path.join(dir, file);
    const stat = fs.statSync(file);
    if (stat && stat.isDirectory()) {
      results = results.concat(walk(file));
    } else {
      if (file.endsWith('.tsx') || file.endsWith('.ts')) {
        results.push(file);
      }
    }
  });
  return results;
};

const files = walk('./src/app');

files.forEach(file => {
  let content = fs.readFileSync(file, 'utf8');
  
  if (content.includes('next/link')) {
    // Replace <Link to="..."> with <Link href="...">
    // also handles to={`...`}
    content = content.replace(/<Link([^>]+)to=/g, "<Link$1href=");
  }
  
  fs.writeFileSync(file, content);
});

console.log("Link href migration complete");
