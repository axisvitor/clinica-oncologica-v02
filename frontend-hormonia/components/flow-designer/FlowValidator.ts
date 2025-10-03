import {
  FlowDesign,
  FlowNode,
  FlowConnection,
  FlowValidationResult,
  FlowValidationError,
  FlowValidationWarning,
  FlowNodeType
} from '../../lib/types/flow-designer'
import {
  getStringFromConfig,
  getNumberFromConfig,
  getArrayFromConfig,
  isValidUrl
} from '../../lib/utils/type-guards'

export class FlowValidator {
  validate(design: FlowDesign): FlowValidationResult {
    const errors: FlowValidationError[] = []
    const warnings: FlowValidationWarning[] = []

    // Basic structure validation
    this.validateBasicStructure(design, errors)
    
    // Node validation
    this.validateNodes(design, errors, warnings)
    
    // Connection validation
    this.validateConnections(design, errors, warnings)
    
    // Flow logic validation
    this.validateFlowLogic(design, errors, warnings)

    return {
      isValid: errors.length === 0,
      errors,
      warnings
    }
  }

  private validateBasicStructure(design: FlowDesign, errors: FlowValidationError[]) {
    // Check for at least one start node
    const startNodes = design.nodes.filter(node => node.type === FlowNodeType.START)
    if (startNodes.length === 0) {
      errors.push({
        id: 'no-start-node',
        type: 'missing_connection',
        message: 'O fluxo deve ter pelo menos um nó de início',
        severity: 'error'
      })
    } else if (startNodes.length > 1) {
      errors.push({
        id: 'multiple-start-nodes',
        type: 'invalid_config',
        message: 'O fluxo deve ter apenas um nó de início',
        severity: 'error'
      })
    }

    // Check for at least one end node
    const endNodes = design.nodes.filter(node => node.type === FlowNodeType.END)
    if (endNodes.length === 0) {
      errors.push({
        id: 'no-end-node',
        type: 'missing_connection',
        message: 'O fluxo deve ter pelo menos um nó de fim',
        severity: 'error'
      })
    }
  }

  private validateNodes(design: FlowDesign, errors: FlowValidationError[], warnings: FlowValidationWarning[]) {
    design.nodes.forEach(node => {
      // Validate node data
      if (!node.data.label || node.data.label.trim() === '') {
        errors.push({
          id: `node-${node.id}-no-label`,
          type: 'invalid_config',
          node_id: node.id,
          message: 'O nó deve ter um rótulo',
          severity: 'error'
        })
      }

      // Type-specific validation
      this.validateNodeByType(node, errors, warnings)

      // Check for isolated nodes (no connections)
      const hasIncoming = design.connections.some(conn => conn.target === node.id)
      const hasOutgoing = design.connections.some(conn => conn.source === node.id)
      
      if (!hasIncoming && node.type !== FlowNodeType.START) {
        warnings.push({
          id: `node-${node.id}-no-incoming`,
          type: 'best_practice',
          node_id: node.id,
          message: 'Nó sem conexões de entrada (exceto nós de início)',
          suggestion: 'Conecte este nó a um nó anterior'
        })
      }

      if (!hasOutgoing && node.type !== FlowNodeType.END) {
        warnings.push({
          id: `node-${node.id}-no-outgoing`,
          type: 'best_practice',
          node_id: node.id,
          message: 'Nó sem conexões de saída (exceto nós de fim)',
          suggestion: 'Conecte este nó a um próximo nó'
        })
      }
    })
  }

  private validateNodeByType(node: FlowNode, errors: FlowValidationError[], warnings: FlowValidationWarning[]) {
    switch (node.type) {
      case FlowNodeType.MESSAGE:
        this.validateMessageNode(node, errors, warnings)
        break
      case FlowNodeType.CONDITION:
        this.validateConditionNode(node, errors, warnings)
        break
      case FlowNodeType.DELAY:
        this.validateDelayNode(node, errors, warnings)
        break
      case FlowNodeType.ACTION:
        this.validateActionNode(node, errors, warnings)
        break
      case FlowNodeType.AI_RESPONSE:
        this.validateAIResponseNode(node, errors, warnings)
        break
      case FlowNodeType.QUIZ:
        this.validateQuizNode(node, errors, warnings)
        break
      case FlowNodeType.WEBHOOK:
        this.validateWebhookNode(node, errors, warnings)
        break
    }
  }

  private validateMessageNode(node: FlowNode, errors: FlowValidationError[], warnings: FlowValidationWarning[]) {
    const config = node.data.config
    
    const content = getStringFromConfig(config, 'content')
    if (!content || content.trim() === '') {
      errors.push({
        id: `node-${node.id}-no-content`,
        type: 'invalid_config',
        node_id: node.id,
        message: 'Mensagem deve ter conteúdo',
        severity: 'error'
      })
    }

    if (content && content.length > 1000) {
      warnings.push({
        id: `node-${node.id}-long-content`,
        type: 'best_practice',
        node_id: node.id,
        message: 'Mensagem muito longa (>1000 caracteres)',
        suggestion: 'Considere dividir em mensagens menores'
      })
    }
  }

  private validateConditionNode(node: FlowNode, errors: FlowValidationError[], warnings: FlowValidationWarning[]) {
    const config = node.data.config
    
    const conditions = getArrayFromConfig(config, 'conditions')
    if (conditions.length === 0) {
      errors.push({
        id: `node-${node.id}-no-conditions`,
        type: 'invalid_config',
        node_id: node.id,
        message: 'Nó de condição deve ter pelo menos uma condição',
        severity: 'error'
      })
    }
  }

  private validateDelayNode(node: FlowNode, errors: FlowValidationError[], warnings: FlowValidationWarning[]) {
    const config = node.data.config
    
    const duration = getNumberFromConfig(config, 'duration')
    if (duration <= 0) {
      errors.push({
        id: `node-${node.id}-invalid-duration`,
        type: 'invalid_config',
        node_id: node.id,
        message: 'Duração do atraso deve ser maior que zero',
        severity: 'error'
      })
    }

    const unit = getStringFromConfig(config, 'unit')
    if (duration > 365 && unit === 'days') {
      warnings.push({
        id: `node-${node.id}-long-delay`,
        type: 'performance',
        node_id: node.id,
        message: 'Atraso muito longo (>365 dias)',
        suggestion: 'Considere usar um atraso menor'
      })
    }
  }

  private validateActionNode(node: FlowNode, errors: FlowValidationError[], warnings: FlowValidationWarning[]) {
    const config = node.data.config
    
    const actionType = getStringFromConfig(config, 'action_type')
    if (!actionType) {
      errors.push({
        id: `node-${node.id}-no-action-type`,
        type: 'invalid_config',
        node_id: node.id,
        message: 'Tipo de ação deve ser especificado',
        severity: 'error'
      })
    }
  }

  private validateAIResponseNode(node: FlowNode, errors: FlowValidationError[], warnings: FlowValidationWarning[]) {
    const config = node.data.config
    
    const promptTemplate = getStringFromConfig(config, 'prompt_template')
    if (!promptTemplate || promptTemplate.trim() === '') {
      errors.push({
        id: `node-${node.id}-no-prompt`,
        type: 'invalid_config',
        node_id: node.id,
        message: 'Template do prompt é obrigatório',
        severity: 'error'
      })
    }

    const fallbackMessage = getStringFromConfig(config, 'fallback_message')
    if (!fallbackMessage) {
      warnings.push({
        id: `node-${node.id}-no-fallback`,
        type: 'best_practice',
        node_id: node.id,
        message: 'Recomendado ter mensagem de fallback',
        suggestion: 'Adicione uma mensagem caso a IA falhe'
      })
    }
  }

  private validateQuizNode(node: FlowNode, errors: FlowValidationError[], warnings: FlowValidationWarning[]) {
    const config = node.data.config
    
    const questions = getArrayFromConfig(config, 'questions')
    if (questions.length === 0) {
      errors.push({
        id: `node-${node.id}-no-questions`,
        type: 'invalid_config',
        node_id: node.id,
        message: 'Quiz deve ter pelo menos uma pergunta',
        severity: 'error'
      })
    }
  }

  private validateWebhookNode(node: FlowNode, errors: FlowValidationError[], warnings: FlowValidationWarning[]) {
    const config = node.data.config
    
    const url = getStringFromConfig(config, 'url')
    if (!url || !this.isValidUrl(url)) {
      errors.push({
        id: `node-${node.id}-invalid-url`,
        type: 'invalid_config',
        node_id: node.id,
        message: 'URL do webhook deve ser válida',
        severity: 'error'
      })
    }
  }

  private validateConnections(design: FlowDesign, errors: FlowValidationError[], warnings: FlowValidationWarning[]) {
    design.connections.forEach(connection => {
      // Check if source and target nodes exist
      const sourceNode = design.nodes.find(node => node.id === connection.source)
      const targetNode = design.nodes.find(node => node.id === connection.target)

      if (!sourceNode) {
        errors.push({
          id: `connection-${connection.id}-invalid-source`,
          type: 'missing_connection',
          connection_id: connection.id,
          message: 'Nó de origem da conexão não existe',
          severity: 'error'
        })
      }

      if (!targetNode) {
        errors.push({
          id: `connection-${connection.id}-invalid-target`,
          type: 'missing_connection',
          connection_id: connection.id,
          message: 'Nó de destino da conexão não existe',
          severity: 'error'
        })
      }

      // Check for self-connections
      if (connection.source === connection.target) {
        errors.push({
          id: `connection-${connection.id}-self-connection`,
          type: 'invalid_config',
          connection_id: connection.id,
          message: 'Nó não pode se conectar a si mesmo',
          severity: 'error'
        })
      }
    })

    // Check for duplicate connections
    const connectionPairs = design.connections.map(conn => `${conn.source}-${conn.target}`)
    const duplicates = connectionPairs.filter((pair, index) => connectionPairs.indexOf(pair) !== index)
    
    duplicates.forEach(duplicate => {
      const [source, target] = duplicate.split('-')
      errors.push({
        id: `duplicate-connection-${source}-${target}`,
        type: 'invalid_config',
        message: `Conexão duplicada entre ${source} e ${target}`,
        severity: 'error'
      })
    })
  }

  private validateFlowLogic(design: FlowDesign, errors: FlowValidationError[], warnings: FlowValidationWarning[]) {
    // Check for circular dependencies
    this.detectCircularDependencies(design, errors)
    
    // Check for unreachable nodes
    this.detectUnreachableNodes(design, warnings)
  }

  private detectCircularDependencies(design: FlowDesign, errors: FlowValidationError[]) {
    const visited = new Set<string>()
    const recursionStack = new Set<string>()

    const hasCycle = (nodeId: string): boolean => {
      if (recursionStack.has(nodeId)) {
        return true
      }
      if (visited.has(nodeId)) {
        return false
      }

      visited.add(nodeId)
      recursionStack.add(nodeId)

      const outgoingConnections = design.connections.filter(conn => conn.source === nodeId)
      for (const connection of outgoingConnections) {
        if (hasCycle(connection.target)) {
          return true
        }
      }

      recursionStack.delete(nodeId)
      return false
    }

    design.nodes.forEach(node => {
      if (!visited.has(node.id) && hasCycle(node.id)) {
        errors.push({
          id: `circular-dependency-${node.id}`,
          type: 'circular_dependency',
          node_id: node.id,
          message: 'Dependência circular detectada',
          severity: 'error'
        })
      }
    })
  }

  private detectUnreachableNodes(design: FlowDesign, warnings: FlowValidationWarning[]) {
    const startNodes = design.nodes.filter(node => node.type === FlowNodeType.START)
    if (startNodes.length === 0) return

    const reachable = new Set<string>()
    const queue = [...startNodes.map(node => node.id)]

    while (queue.length > 0) {
      const currentId = queue.shift()!
      if (reachable.has(currentId)) continue

      reachable.add(currentId)
      
      const outgoingConnections = design.connections.filter(conn => conn.source === currentId)
      outgoingConnections.forEach(conn => {
        if (!reachable.has(conn.target)) {
          queue.push(conn.target)
        }
      })
    }

    design.nodes.forEach(node => {
      if (!reachable.has(node.id) && node.type !== FlowNodeType.START) {
        warnings.push({
          id: `unreachable-node-${node.id}`,
          type: 'best_practice',
          node_id: node.id,
          message: 'Nó não é alcançável a partir do início',
          suggestion: 'Conecte este nó ao fluxo principal'
        })
      }
    })
  }

  private isValidUrl(url: string): boolean {
    return isValidUrl(url)
  }
}
