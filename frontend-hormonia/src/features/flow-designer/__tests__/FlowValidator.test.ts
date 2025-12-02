/**
 * @vitest-environment node
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { FlowValidator } from '../FlowValidator'
import { FlowDesign, FlowNode, FlowNodeType, FlowConnection } from '@/types/flow-designer'

// Helper to create a minimal valid flow design
function createEmptyDesign(): FlowDesign {
  return {
    id: 'test-design',
    name: 'Test Flow',
    description: '',
    version: '1.0.0',
    nodes: [],
    connections: [],
    variables: [],
    metadata: {
      author: 'test',
      tags: [],
      category: 'test',
      complexity_level: 'simple'
    },
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString()
  }
}

function createNode(id: string, type: FlowNodeType, label = 'Test Node'): FlowNode {
  return {
    id,
    type,
    position: { x: 0, y: 0 },
    data: {
      label,
      config: {}
    }
  }
}

function createConnection(id: string, source: string, target: string): FlowConnection {
  return { id, source, target }
}

describe('FlowValidator', () => {
  let validator: FlowValidator

  beforeEach(() => {
    validator = new FlowValidator()
  })

  describe('Basic Structure Validation', () => {
    it('should report error when no start node exists', () => {
      const design = createEmptyDesign()
      design.nodes = [
        createNode('1', FlowNodeType.MESSAGE),
        createNode('2', FlowNodeType.END)
      ]
      design.connections = [createConnection('c1', '1', '2')]

      const result = validator.validate(design)

      expect(result.isValid).toBe(false)
      expect(result.errors).toContainEqual(
        expect.objectContaining({
          id: 'no-start-node',
          type: 'missing_connection'
        })
      )
    })

    it('should report error when multiple start nodes exist', () => {
      const design = createEmptyDesign()
      design.nodes = [
        createNode('1', FlowNodeType.START),
        createNode('2', FlowNodeType.START),
        createNode('3', FlowNodeType.END)
      ]
      design.connections = [
        createConnection('c1', '1', '3'),
        createConnection('c2', '2', '3')
      ]

      const result = validator.validate(design)

      expect(result.isValid).toBe(false)
      expect(result.errors).toContainEqual(
        expect.objectContaining({
          id: 'multiple-start-nodes',
          type: 'invalid_config'
        })
      )
    })

    it('should report error when no end node exists', () => {
      const design = createEmptyDesign()
      design.nodes = [
        createNode('1', FlowNodeType.START),
        createNode('2', FlowNodeType.MESSAGE)
      ]
      design.connections = [createConnection('c1', '1', '2')]

      const result = validator.validate(design)

      expect(result.isValid).toBe(false)
      expect(result.errors).toContainEqual(
        expect.objectContaining({
          id: 'no-end-node',
          type: 'missing_connection'
        })
      )
    })

    it('should pass validation for a valid simple flow', () => {
      const design = createEmptyDesign()
      design.nodes = [
        createNode('start', FlowNodeType.START, 'Início'),
        createNode('msg', FlowNodeType.MESSAGE, 'Mensagem'),
        createNode('end', FlowNodeType.END, 'Fim')
      ]
      design.nodes[1].data.config = { content: 'Hello' }
      design.connections = [
        createConnection('c1', 'start', 'msg'),
        createConnection('c2', 'msg', 'end')
      ]

      const result = validator.validate(design)

      expect(result.isValid).toBe(true)
      expect(result.errors).toHaveLength(0)
    })
  })

  describe('Node Validation', () => {
    it('should report error when node has no label', () => {
      const design = createEmptyDesign()
      design.nodes = [
        createNode('start', FlowNodeType.START, ''),
        createNode('end', FlowNodeType.END, 'Fim')
      ]
      design.connections = [createConnection('c1', 'start', 'end')]

      const result = validator.validate(design)

      expect(result.errors).toContainEqual(
        expect.objectContaining({
          type: 'invalid_config',
          node_id: 'start',
          message: 'O nó deve ter um rótulo'
        })
      )
    })

    it('should warn about isolated nodes without incoming connections', () => {
      const design = createEmptyDesign()
      design.nodes = [
        createNode('start', FlowNodeType.START, 'Início'),
        createNode('msg', FlowNodeType.MESSAGE, 'Mensagem'),
        createNode('isolated', FlowNodeType.MESSAGE, 'Isolado'),
        createNode('end', FlowNodeType.END, 'Fim')
      ]
      design.nodes[1].data.config = { content: 'Hello' }
      design.nodes[2].data.config = { content: 'Isolated' }
      design.connections = [
        createConnection('c1', 'start', 'msg'),
        createConnection('c2', 'msg', 'end')
      ]

      const result = validator.validate(design)

      expect(result.warnings).toContainEqual(
        expect.objectContaining({
          type: 'best_practice',
          node_id: 'isolated'
        })
      )
    })
  })

  describe('Message Node Validation', () => {
    it('should report error when message node has no content', () => {
      const design = createEmptyDesign()
      design.nodes = [
        createNode('start', FlowNodeType.START, 'Início'),
        createNode('msg', FlowNodeType.MESSAGE, 'Mensagem'),
        createNode('end', FlowNodeType.END, 'Fim')
      ]
      design.nodes[1].data.config = { content: '' }
      design.connections = [
        createConnection('c1', 'start', 'msg'),
        createConnection('c2', 'msg', 'end')
      ]

      const result = validator.validate(design)

      expect(result.errors).toContainEqual(
        expect.objectContaining({
          type: 'invalid_config',
          node_id: 'msg',
          message: 'Mensagem deve ter conteúdo'
        })
      )
    })

    it('should warn about long messages', () => {
      const design = createEmptyDesign()
      design.nodes = [
        createNode('start', FlowNodeType.START, 'Início'),
        createNode('msg', FlowNodeType.MESSAGE, 'Mensagem'),
        createNode('end', FlowNodeType.END, 'Fim')
      ]
      design.nodes[1].data.config = { content: 'A'.repeat(1001) }
      design.connections = [
        createConnection('c1', 'start', 'msg'),
        createConnection('c2', 'msg', 'end')
      ]

      const result = validator.validate(design)

      expect(result.warnings).toContainEqual(
        expect.objectContaining({
          type: 'best_practice',
          node_id: 'msg',
          message: 'Mensagem muito longa (>1000 caracteres)'
        })
      )
    })
  })

  describe('Condition Node Validation', () => {
    it('should report error when condition node has no conditions', () => {
      const design = createEmptyDesign()
      design.nodes = [
        createNode('start', FlowNodeType.START, 'Início'),
        createNode('cond', FlowNodeType.CONDITION, 'Condição'),
        createNode('end', FlowNodeType.END, 'Fim')
      ]
      design.nodes[1].data.config = { conditions: [] }
      design.connections = [
        createConnection('c1', 'start', 'cond'),
        createConnection('c2', 'cond', 'end')
      ]

      const result = validator.validate(design)

      expect(result.errors).toContainEqual(
        expect.objectContaining({
          type: 'invalid_config',
          node_id: 'cond',
          message: 'Nó de condição deve ter pelo menos uma condição'
        })
      )
    })
  })

  describe('Delay Node Validation', () => {
    it('should report error when delay duration is zero or negative', () => {
      const design = createEmptyDesign()
      design.nodes = [
        createNode('start', FlowNodeType.START, 'Início'),
        createNode('delay', FlowNodeType.DELAY, 'Atraso'),
        createNode('end', FlowNodeType.END, 'Fim')
      ]
      design.nodes[1].data.config = { duration: 0, unit: 'minutes' }
      design.connections = [
        createConnection('c1', 'start', 'delay'),
        createConnection('c2', 'delay', 'end')
      ]

      const result = validator.validate(design)

      expect(result.errors).toContainEqual(
        expect.objectContaining({
          type: 'invalid_config',
          node_id: 'delay',
          message: 'Duração do atraso deve ser maior que zero'
        })
      )
    })
  })

  describe('Connection Validation', () => {
    it('should report error for self-connections', () => {
      const design = createEmptyDesign()
      design.nodes = [
        createNode('start', FlowNodeType.START, 'Início'),
        createNode('msg', FlowNodeType.MESSAGE, 'Mensagem'),
        createNode('end', FlowNodeType.END, 'Fim')
      ]
      design.nodes[1].data.config = { content: 'Hello' }
      design.connections = [
        createConnection('c1', 'start', 'msg'),
        createConnection('c2', 'msg', 'msg'), // Self-connection
        createConnection('c3', 'msg', 'end')
      ]

      const result = validator.validate(design)

      expect(result.errors).toContainEqual(
        expect.objectContaining({
          type: 'invalid_config',
          connection_id: 'c2',
          message: 'Nó não pode se conectar a si mesmo'
        })
      )
    })

    it('should report error for invalid source node', () => {
      const design = createEmptyDesign()
      design.nodes = [
        createNode('start', FlowNodeType.START, 'Início'),
        createNode('end', FlowNodeType.END, 'Fim')
      ]
      design.connections = [
        createConnection('c1', 'nonexistent', 'end')
      ]

      const result = validator.validate(design)

      expect(result.errors).toContainEqual(
        expect.objectContaining({
          type: 'missing_connection',
          connection_id: 'c1',
          message: 'Nó de origem da conexão não existe'
        })
      )
    })

    it('should report error for duplicate connections', () => {
      const design = createEmptyDesign()
      design.nodes = [
        createNode('start', FlowNodeType.START, 'Início'),
        createNode('end', FlowNodeType.END, 'Fim')
      ]
      design.connections = [
        createConnection('c1', 'start', 'end'),
        createConnection('c2', 'start', 'end')
      ]

      const result = validator.validate(design)

      expect(result.errors).toContainEqual(
        expect.objectContaining({
          type: 'invalid_config',
          message: expect.stringContaining('Conexão duplicada')
        })
      )
    })
  })

  describe('Flow Logic Validation', () => {
    it('should detect circular dependencies', () => {
      const design = createEmptyDesign()
      design.nodes = [
        createNode('start', FlowNodeType.START, 'Início'),
        createNode('a', FlowNodeType.MESSAGE, 'A'),
        createNode('b', FlowNodeType.MESSAGE, 'B'),
        createNode('end', FlowNodeType.END, 'Fim')
      ]
      design.nodes[1].data.config = { content: 'A' }
      design.nodes[2].data.config = { content: 'B' }
      design.connections = [
        createConnection('c1', 'start', 'a'),
        createConnection('c2', 'a', 'b'),
        createConnection('c3', 'b', 'a'), // Creates cycle
        createConnection('c4', 'b', 'end')
      ]

      const result = validator.validate(design)

      expect(result.errors).toContainEqual(
        expect.objectContaining({
          type: 'circular_dependency'
        })
      )
    })

    it('should warn about unreachable nodes', () => {
      const design = createEmptyDesign()
      design.nodes = [
        createNode('start', FlowNodeType.START, 'Início'),
        createNode('msg', FlowNodeType.MESSAGE, 'Mensagem'),
        createNode('unreachable', FlowNodeType.MESSAGE, 'Inacessível'),
        createNode('end', FlowNodeType.END, 'Fim')
      ]
      design.nodes[1].data.config = { content: 'Hello' }
      design.nodes[2].data.config = { content: 'Never reached' }
      design.connections = [
        createConnection('c1', 'start', 'msg'),
        createConnection('c2', 'msg', 'end')
        // unreachable has no incoming connections from start
      ]

      const result = validator.validate(design)

      expect(result.warnings).toContainEqual(
        expect.objectContaining({
          type: 'best_practice',
          node_id: 'unreachable',
          message: 'Nó não é alcançável a partir do início'
        })
      )
    })
  })

  describe('Webhook Node Validation', () => {
    it('should report error for invalid webhook URL', () => {
      const design = createEmptyDesign()
      design.nodes = [
        createNode('start', FlowNodeType.START, 'Início'),
        createNode('webhook', FlowNodeType.WEBHOOK, 'Webhook'),
        createNode('end', FlowNodeType.END, 'Fim')
      ]
      design.nodes[1].data.config = { url: 'not-a-valid-url' }
      design.connections = [
        createConnection('c1', 'start', 'webhook'),
        createConnection('c2', 'webhook', 'end')
      ]

      const result = validator.validate(design)

      expect(result.errors).toContainEqual(
        expect.objectContaining({
          type: 'invalid_config',
          node_id: 'webhook',
          message: 'URL do webhook deve ser válida'
        })
      )
    })

    it('should accept valid webhook URL', () => {
      const design = createEmptyDesign()
      design.nodes = [
        createNode('start', FlowNodeType.START, 'Início'),
        createNode('webhook', FlowNodeType.WEBHOOK, 'Webhook'),
        createNode('end', FlowNodeType.END, 'Fim')
      ]
      design.nodes[1].data.config = { url: 'https://api.example.com/webhook' }
      design.connections = [
        createConnection('c1', 'start', 'webhook'),
        createConnection('c2', 'webhook', 'end')
      ]

      const result = validator.validate(design)

      const webhookErrors = result.errors.filter(e => e.node_id === 'webhook')
      expect(webhookErrors).toHaveLength(0)
    })
  })

  describe('AI Response Node Validation', () => {
    it('should report error when prompt template is missing', () => {
      const design = createEmptyDesign()
      design.nodes = [
        createNode('start', FlowNodeType.START, 'Início'),
        createNode('ai', FlowNodeType.AI_RESPONSE, 'AI'),
        createNode('end', FlowNodeType.END, 'Fim')
      ]
      design.nodes[1].data.config = { prompt_template: '' }
      design.connections = [
        createConnection('c1', 'start', 'ai'),
        createConnection('c2', 'ai', 'end')
      ]

      const result = validator.validate(design)

      expect(result.errors).toContainEqual(
        expect.objectContaining({
          type: 'invalid_config',
          node_id: 'ai',
          message: 'Template do prompt é obrigatório'
        })
      )
    })

    it('should warn when fallback message is missing', () => {
      const design = createEmptyDesign()
      design.nodes = [
        createNode('start', FlowNodeType.START, 'Início'),
        createNode('ai', FlowNodeType.AI_RESPONSE, 'AI'),
        createNode('end', FlowNodeType.END, 'Fim')
      ]
      design.nodes[1].data.config = { prompt_template: 'Respond to {message}' }
      design.connections = [
        createConnection('c1', 'start', 'ai'),
        createConnection('c2', 'ai', 'end')
      ]

      const result = validator.validate(design)

      expect(result.warnings).toContainEqual(
        expect.objectContaining({
          type: 'best_practice',
          node_id: 'ai',
          message: 'Recomendado ter mensagem de fallback'
        })
      )
    })
  })

  describe('Quiz Node Validation', () => {
    it('should report error when quiz has no questions', () => {
      const design = createEmptyDesign()
      design.nodes = [
        createNode('start', FlowNodeType.START, 'Início'),
        createNode('quiz', FlowNodeType.QUIZ, 'Quiz'),
        createNode('end', FlowNodeType.END, 'Fim')
      ]
      design.nodes[1].data.config = { questions: [] }
      design.connections = [
        createConnection('c1', 'start', 'quiz'),
        createConnection('c2', 'quiz', 'end')
      ]

      const result = validator.validate(design)

      expect(result.errors).toContainEqual(
        expect.objectContaining({
          type: 'invalid_config',
          node_id: 'quiz',
          message: 'Quiz deve ter pelo menos uma pergunta'
        })
      )
    })
  })
})
