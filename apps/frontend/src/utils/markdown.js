import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'

const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: false,
  highlight(code, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return `<pre class="hljs-block"><code class="hljs language-${lang}">${hljs.highlight(code, { language: lang, ignoreIllegals: true }).value}</code></pre>`
      } catch (e) {
        console.debug('highlight.js 高亮失败，降级为纯文本:', lang, e)
      }
    }
    return `<pre class="hljs-block"><code class="hljs">${md.utils.escapeHtml(code)}</code></pre>`
  },
})

export function renderMarkdown(text) {
  if (!text) return ''
  return md.render(text)
}
