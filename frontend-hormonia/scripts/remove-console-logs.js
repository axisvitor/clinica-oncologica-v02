#!/usr/bin/env node
/**
 * Script to find and replace console.log statements with logger
 *
 * QUALITY FIX #7: Remove console.logs from production code
 *
 * This script:
 * 1. Scans all TypeScript/JavaScript files
 * 2. Finds console.log/warn/error/debug statements
 * 3. Replaces with appropriate logger calls
 * 4. Reports statistics
 *
 * Usage:
 *   node scripts/remove-console-logs.js [--dry-run] [--path=src]
 *
 * Options:
 *   --dry-run    Show what would be changed without modifying files
 *   --path       Specify directory to scan (default: src)
 *   --exclude    Exclude pattern (default: node_modules,dist)
 */

const fs = require('fs');
const path = require('path');

// Configuration
const config = {
  dryRun: process.argv.includes('--dry-run'),
  targetPath: process.argv.find(arg => arg.startsWith('--path='))?.split('=')[1] || 'src',
  exclude: process.argv.find(arg => arg.startsWith('--exclude='))?.split('=')[1]?.split(',') || ['node_modules', 'dist', '.git'],
};

// Statistics
const stats = {
  filesScanned: 0,
  filesModified: 0,
  consoleLogsFound: 0,
  consoleLogsReplaced: 0,
  errors: [],
};

/**
 * Check if file should be excluded
 */
function shouldExclude(filePath) {
  return config.exclude.some(pattern => filePath.includes(pattern));
}

/**
 * Check if file is TypeScript/JavaScript
 */
function isTargetFile(filePath) {
  return /\.(ts|tsx|js|jsx)$/.test(filePath);
}

/**
 * Get all files recursively
 */
function getAllFiles(dirPath, arrayOfFiles = []) {
  const files = fs.readdirSync(dirPath);

  files.forEach(file => {
    const fullPath = path.join(dirPath, file);

    if (shouldExclude(fullPath)) {
      return;
    }

    if (fs.statSync(fullPath).isDirectory()) {
      arrayOfFiles = getAllFiles(fullPath, arrayOfFiles);
    } else if (isTargetFile(fullPath)) {
      arrayOfFiles.push(fullPath);
    }
  });

  return arrayOfFiles;
}

/**
 * Replace console statements in content
 */
function replaceConsoleLogs(content, filePath) {
  let modified = false;
  let replacements = 0;

  // Add logger import if not present
  const hasLoggerImport = /import\s+.*\s+from\s+['"]@\/utils\/logger['"]/.test(content) ||
                          /import\s+.*\s+from\s+['"].*\/utils\/logger['"]/.test(content);

  // Patterns to replace
  const patterns = [
    {
      // console.log(...) -> logger.info(...)
      regex: /console\.log\(/g,
      replacement: 'logger.info(',
      level: 'info',
    },
    {
      // console.debug(...) -> logger.debug(...)
      regex: /console\.debug\(/g,
      replacement: 'logger.debug(',
      level: 'debug',
    },
    {
      // console.warn(...) -> logger.warn(...)
      regex: /console\.warn\(/g,
      replacement: 'logger.warn(',
      level: 'warn',
    },
    {
      // console.error(...) -> logger.error(...)
      regex: /console\.error\(/g,
      replacement: 'logger.error(',
      level: 'error',
    },
    {
      // console.info(...) -> logger.info(...)
      regex: /console\.info\(/g,
      replacement: 'logger.info(',
      level: 'info',
    },
  ];

  // Count occurrences
  let totalOccurrences = 0;
  patterns.forEach(pattern => {
    const matches = content.match(pattern.regex);
    if (matches) {
      totalOccurrences += matches.length;
    }
  });

  if (totalOccurrences === 0) {
    return { content, modified: false, replacements: 0 };
  }

  stats.consoleLogsFound += totalOccurrences;

  // Replace console statements
  let newContent = content;
  patterns.forEach(pattern => {
    const matches = newContent.match(pattern.regex);
    if (matches) {
      newContent = newContent.replace(pattern.regex, pattern.replacement);
      replacements += matches.length;
      modified = true;
    }
  });

  // Add logger import if needed and not present
  if (modified && !hasLoggerImport) {
    // Determine import path based on file location
    const relativePath = path.relative(path.dirname(filePath), path.join(config.targetPath, 'utils', 'logger'));
    const importPath = relativePath.startsWith('..') ? relativePath : './' + relativePath;
    const cleanPath = importPath.replace(/\\/g, '/').replace(/\.ts$/, '');

    // Find position to insert import (after existing imports or at top)
    const lastImportMatch = newContent.match(/import\s+.*\s+from\s+['"].*['"];?\n/g);
    if (lastImportMatch) {
      const lastImport = lastImportMatch[lastImportMatch.length - 1];
      const lastImportIndex = newContent.lastIndexOf(lastImport);
      const insertPosition = lastImportIndex + lastImport.length;

      newContent =
        newContent.slice(0, insertPosition) +
        `import { logger } from '${cleanPath}';\n` +
        newContent.slice(insertPosition);
    } else {
      // No imports, add at top
      newContent = `import { logger } from '${cleanPath}';\n\n` + newContent;
    }
  }

  return { content: newContent, modified, replacements };
}

/**
 * Process a single file
 */
function processFile(filePath) {
  stats.filesScanned++;

  try {
    const content = fs.readFileSync(filePath, 'utf8');
    const result = replaceConsoleLogs(content, filePath);

    if (result.modified) {
      stats.filesModified++;
      stats.consoleLogsReplaced += result.replacements;

      console.log(`✏️  ${filePath}`);
      console.log(`   └─ Replaced ${result.replacements} console statement(s)`);

      if (!config.dryRun) {
        fs.writeFileSync(filePath, result.content, 'utf8');
      }
    }
  } catch (error) {
    stats.errors.push({ file: filePath, error: error.message });
    console.error(`❌ Error processing ${filePath}: ${error.message}`);
  }
}

/**
 * Main execution
 */
function main() {
  console.log('🔍 Scanning for console.log statements...\n');
  console.log(`Mode: ${config.dryRun ? 'DRY RUN (no files will be modified)' : 'LIVE (files will be modified)'}`);
  console.log(`Path: ${config.targetPath}`);
  console.log(`Exclude: ${config.exclude.join(', ')}\n`);

  const startTime = Date.now();

  // Get all files
  const files = getAllFiles(config.targetPath);
  console.log(`Found ${files.length} files to scan\n`);

  // Process each file
  files.forEach(processFile);

  const duration = ((Date.now() - startTime) / 1000).toFixed(2);

  // Print summary
  console.log('\n' + '='.repeat(60));
  console.log('📊 SUMMARY');
  console.log('='.repeat(60));
  console.log(`Files scanned:       ${stats.filesScanned}`);
  console.log(`Files modified:      ${stats.filesModified}`);
  console.log(`Console logs found:  ${stats.consoleLogsFound}`);
  console.log(`Console logs replaced: ${stats.consoleLogsReplaced}`);
  console.log(`Errors:              ${stats.errors.length}`);
  console.log(`Duration:            ${duration}s`);
  console.log('='.repeat(60));

  if (stats.errors.length > 0) {
    console.log('\n❌ ERRORS:');
    stats.errors.forEach(({ file, error }) => {
      console.log(`   ${file}: ${error}`);
    });
  }

  if (config.dryRun && stats.filesModified > 0) {
    console.log('\n💡 TIP: Run without --dry-run to apply changes');
  }

  if (!config.dryRun && stats.filesModified > 0) {
    console.log('\n✅ Changes applied successfully!');
    console.log('📝 Next steps:');
    console.log('   1. Review the changes with: git diff');
    console.log('   2. Test the application');
    console.log('   3. Commit: git commit -m "refactor: replace console.logs with logger"');
  }

  if (stats.consoleLogsFound === 0) {
    console.log('\n🎉 No console.log statements found! Code is clean.');
  }

  // Exit with error code if there were errors
  process.exit(stats.errors.length > 0 ? 1 : 0);
}

// Run script
main();
