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

// Also apply to components and lib maybe? No, let's just do app directory
const files = [...walk('./src/app'), ...walk('./src/components'), ...walk('./src/hooks')];

files.forEach(file => {
  let content = fs.readFileSync(file, 'utf8');
  
  // Replace imports like from '../components/Logo' to '@/components/Logo'
  // Regex to match from '../... or from '../../...
  content = content.replace(/from\s+['"]\.\.\/\.\.\/(components|lib|hooks|store|screens)(.*?)['"]/g, "from '@/$1$2'");
  content = content.replace(/from\s+['"]\.\.\/(components|lib|hooks|store|screens)(.*?)['"]/g, "from '@/$1$2'");
  
  fs.writeFileSync(file, content);
});

console.log("Imports migration complete");
