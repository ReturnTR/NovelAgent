import hljs from 'highlight.js';

export const renderMarkdown = (content: string): string => {
  let html = content
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Tables
  html = renderTables(html);

  // Code blocks with syntax highlighting
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
    const trimmedCode = code.trim();
    const validLang = lang && hljs.getLanguage(lang);
    const highlighted = validLang
      ? hljs.highlight(trimmedCode, { language: lang }).value
      : hljs.highlightAuto(trimmedCode).value;
    return `<pre class="code-block"><code class="hljs ${lang ? `language-${lang}` : ''}">${highlighted}</code></pre>`;
  });

  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');

  // Bold
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

  // Italic
  html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');

  // Headers
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
  html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
  html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');

  // Links
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" class="md-link">$1</a>');

  // Lists - handle multi-line list items
  html = html.replace(/^[\s]*[-*]\s+(.+)$/gm, '<li>$1</li>');
  html = html.replace(/(<li>.*?<\/li>)(\s*<li>.*?<\/li>)*/g, (match) => {
    return `<ul class="md-list">${match}</ul>`;
  });

  // Horizontal rule
  html = html.replace(/^---$/gm, '<hr class="md-hr" />');

  // Blockquotes
  html = html.replace(/^>\s+(.+)$/gm, '<blockquote class="md-blockquote">$1</blockquote>');

  // Paragraphs - handle line breaks more intelligently
  html = html.replace(/\n\n/g, '</p><p class="md-paragraph">');
  html = html.replace(/\n(?!\s*$)/g, '<br>');

  // Wrap in paragraph if not already wrapped
  if (!html.startsWith('<p') && !html.startsWith('<pre') && !html.startsWith('<ul') && !html.startsWith('<table')) {
    html = `<p class="md-paragraph">${html}</p>`;
  }

  // Clean up empty paragraphs
  html = html.replace(/<p class="md-paragraph"><\/p>/g, '');
  html = html.replace(/<p class="md-paragraph">(\s*<br>\s*)+<\/p>/g, '');

  return html;
};

function renderTables(html: string): string {
  // Match markdown tables
  const tableRegex = /\|(.+)\|\n\|[-:\s|]+\|\n((?:\|.+\|\n?)+)/g;

  return html.replace(tableRegex, (_, headerRow, bodyRows) => {
    // Parse header
    const headers = headerRow.split('|').map((h: string) => h.trim()).filter(Boolean);

    // Parse body rows
    const rows = bodyRows.trim().split('\n').map((row: string) =>
      row.split('|').map((cell: string) => cell.trim()).filter(Boolean)
    );

    let tableHtml = '<div class="table-wrapper"><table class="md-table">';

    // Header
    tableHtml += '<thead><tr>';
    headers.forEach((header: string) => {
      tableHtml += `<th>${header}</th>`;
    });
    tableHtml += '</tr></thead>';

    // Body
    tableHtml += '<tbody>';
    rows.forEach((row: string[]) => {
      tableHtml += '<tr>';
      row.forEach((cell: string) => {
        tableHtml += `<td>${cell}</td>`;
      });
      tableHtml += '</tr>';
    });
    tableHtml += '</tbody></table></div>';

    return tableHtml;
  });
}

export const syntaxHighlightJson = (obj: unknown): string => {
  const json = JSON.stringify(obj, null, 2);
  return json.replace(
    /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g,
    (match: string) => {
      let cls = 'json-number';
      if (/^"/.test(match)) {
        if (/:$/.test(match)) {
          cls = 'json-key';
          match = match.slice(0, -1) + '</span>:';
          return `<span class="${cls}">${match}`;
        } else {
          cls = 'json-string';
        }
      } else if (/true|false/.test(match)) {
        cls = 'json-boolean';
      } else if (/null/.test(match)) {
        cls = 'json-null';
      }
      return `<span class="${cls}">${match}</span>`;
    }
  );
};