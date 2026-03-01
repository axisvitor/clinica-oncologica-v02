import { FlowDesign, FlowNodeType } from '@/types/flow-designer'

export function createTestDesign(): FlowDesign {
  return {
    id: 'test-design',
    name: 'Test Flow',
    description: 'A test flow',
    version: '1.0.0',
    nodes: [
      {
        id: 'start-1',
        type: FlowNodeType.START,
        position: { x: 100, y: 100 },
        data: { label: 'Início', config: {} },
      },
      {
        id: 'msg-1',
        type: FlowNodeType.MESSAGE,
        position: { x: 100, y: 200 },
        data: { label: 'Mensagem', config: { content: 'Olá!' } },
      },
      {
        id: 'end-1',
        type: FlowNodeType.END,
        position: { x: 100, y: 300 },
        data: { label: 'Fim', config: {} },
      },
    ],
    connections: [
      { id: 'c1', source: 'start-1', target: 'msg-1' },
      { id: 'c2', source: 'msg-1', target: 'end-1' },
    ],
    variables: [],
    metadata: {
      author: 'test',
      tags: [],
      category: 'test',
      complexity_level: 'simple',
    },
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  }
}
