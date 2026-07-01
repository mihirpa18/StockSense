import React from 'react'

export function renderMarkdown(text) {
  if (!text) return null

  // Split into blocks by double newlines
  const blocks = text.split(/\n\n+/)

  return blocks.map((block, blockIdx) => {
    const trimmedBlock = block.trim()
    if (!trimmedBlock) return null

    // Check if it's a bullet list
    if (trimmedBlock.startsWith('- ') || trimmedBlock.startsWith('* ') || trimmedBlock.startsWith('• ')) {
      const items = trimmedBlock.split(/\n/)
      return (
        <ul key={blockIdx} style={{ paddingLeft: '20px', margin: '8px 0', listStyleType: 'disc' }}>
          {items.map((item, itemIdx) => {
            const content = item.replace(/^[-*•]\s+/, '')
            return (
              <li key={itemIdx} style={{ marginBottom: '4px', lineHeight: '1.5' }}>
                {parseInlineMarkdown(content)}
              </li>
            )
          })}
        </ul>
      )
    }

    // Check if it's a numbered list
    if (/^\d+\.\s+/.test(trimmedBlock)) {
      const items = trimmedBlock.split(/\n/)
      return (
        <ol key={blockIdx} style={{ paddingLeft: '20px', margin: '8px 0', listStyleType: 'decimal' }}>
          {items.map((item, itemIdx) => {
            const content = item.replace(/^\d+\.\s+/, '')
            return (
              <li key={itemIdx} style={{ marginBottom: '4px', lineHeight: '1.5' }}>
                {parseInlineMarkdown(content)}
              </li>
            )
          })}
        </ol>
      )
    }

    // Check if it's a heading
    if (trimmedBlock.startsWith('#')) {
      const match = trimmedBlock.match(/^(#{1,6})\s+(.*)$/)
      if (match) {
        const level = match[1].length
        const headingText = match[2]
        const Tag = `h${Math.min(level + 2, 6)}` // Scale down to match chat sizing
        return (
          <Tag key={blockIdx} style={{ margin: '12px 0 6px 0', fontWeight: '700', color: 'var(--text)' }}>
            {parseInlineMarkdown(headingText)}
          </Tag>
        )
      }
    }

    // Default paragraph
    const lines = trimmedBlock.split('\n')
    return (
      <p key={blockIdx} style={{ margin: '8px 0', lineHeight: '1.6' }}>
        {lines.map((line, lineIdx) => (
          <span key={lineIdx}>
            {lineIdx > 0 && <br />}
            {parseInlineMarkdown(line)}
          </span>
        ))}
      </p>
    )
  })
}

function parseInlineMarkdown(text) {
  const regex = /(\*\*|__)(.*?)\1|(\*|_)(.*?)\3/g
  const parts = []
  let lastIndex = 0
  let match

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.substring(lastIndex, match.index))
    }

    if (match[1]) {
      // Bold
      parts.push(<strong key={match.index} style={{ fontWeight: '700', color: 'var(--text)' }}>{match[2]}</strong>)
    } else if (match[3]) {
      // Italic
      parts.push(<em key={match.index} style={{ fontStyle: 'italic' }}>{match[4]}</em>)
    }

    lastIndex = regex.lastIndex
  }

  if (lastIndex < text.length) {
    parts.push(text.substring(lastIndex))
  }

  return parts.length > 0 ? parts : text
}

export default function Markdown({ content }) {
  return <div className="markdown-body">{renderMarkdown(content)}</div>
}
