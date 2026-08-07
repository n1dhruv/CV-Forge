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
  if (!file.endsWith('page.tsx') && !file.endsWith('layout.tsx')) return;
  
  let content = fs.readFileSync(file, 'utf8');
  
  // Add use client if it's a page and doesn't have it
  if (file.endsWith('page.tsx') && !content.includes('"use client"')) {
    content = '"use client"\n\n' + content;
  }
  
  // Replace react-router-dom imports
  if (content.includes('react-router-dom')) {
    // Specific replacements
    content = content.replace(/import\s+{\s*Link\s*}\s+from\s+'react-router-dom'/g, "import Link from 'next/link'");
    content = content.replace(/import\s+{\s*Link\s*,\s*useSearchParams\s*}\s+from\s+'react-router-dom'/g, "import Link from 'next/link'\nimport { useSearchParams } from 'next/navigation'");
    content = content.replace(/import\s+{\s*Link\s*,\s*useLocation\s*,\s*useSearchParams\s*}\s+from\s+'react-router-dom'/g, "import Link from 'next/link'\nimport { usePathname, useSearchParams } from 'next/navigation'");
    content = content.replace(/import\s+{\s*Link\s*,\s*Navigate\s*,\s*useNavigate\s*}\s+from\s+'react-router-dom'/g, "import Link from 'next/link'\nimport { useRouter } from 'next/navigation'");
    content = content.replace(/import\s+{\s*Link\s*,\s*useNavigate\s*}\s+from\s+'react-router-dom'/g, "import Link from 'next/link'\nimport { useRouter } from 'next/navigation'");
    
    // Also replace usage of useNavigate with useRouter
    content = content.replace(/useNavigate\(\)/g, "useRouter()");
    
    // Replace useLocation with usePathname
    content = content.replace(/const\s+location\s*=\s*useLocation\(\)/g, "const pathname = usePathname()");
    content = content.replace(/location\.pathname/g, "pathname");
    
    // For Navigate component, it's harder, but we can replace it in AuthPage
    content = content.replace(/<Navigate\s+to="([^"]+)"\s+replace\s*\/>/g, "null /* TODO: Navigate to $1 */");
  }
  
  fs.writeFileSync(file, content);
});

console.log("Migration script complete");
