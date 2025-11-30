/**
 * Template Converters
 *
 * Utility functions to convert between API template format and FlowDesigner format.
 */

import type { FlowTemplate, FlowTemplateStep, FlowTemplateCreate } from '@/hooks/useTemplates';
import type { FlowDesign, FlowNode, FlowConnection } from '@/lib/types/flow-designer';
import { logger } from '@/lib/logger';

// Valid message types based on backend enum
const VALID_MESSAGE_TYPES = ['text', 'image', 'audio', 'video', 'document'];

/**
 * Convert FlowTemplate to FlowDesign format for FlowDesigner
 */
export function convertTemplateToDesign(template: FlowTemplate): FlowDesign {
  // Handle both array and dict formats for steps
  let stepsArray: FlowTemplateStep[] = [];

  if (Array.isArray(template.steps)) {
    stepsArray = template.steps;
  } else if (template.steps && typeof template.steps === 'object') {
    // Convert dict to array
    stepsArray = Object.values(template.steps) as FlowTemplateStep[];
  }

  const nodes: FlowNode[] = stepsArray.map((step: FlowTemplateStep, index: number) => ({
    id: `node-${index}`,
    type: (step.message_type || 'message') as import('@/lib/types/flow-designer').FlowNodeType,
    position: { x: 100 + index * 250, y: 100 },
    data: {
      label: step.intent || 'Message',
      description: step.base_content || '',
      config: {
        content: step.base_content || '',
        aiInstructions: step.ai_instructions || '',
        personalizationHints: step.personalization_hints || [],
      },
    },
  }));

  const connections: FlowConnection[] = nodes.slice(0, -1).map((node, index) => ({
    id: `conn-${index}`,
    source: node.id,
    target: nodes[index + 1]?.id || '',
  }));

  return {
    id: template.id,
    name: template.template_name,
    description: template.description || '',
    version: String(template.version_number || 1),
    nodes,
    connections,
    variables: [],
    metadata: {
      author: 'system',
      tags: [template.kind_key],
      category: template.kind_key,
      complexity_level: 'simple',
    },
    created_at: template.created_at || new Date().toISOString(),
    updated_at: template.updated_at || new Date().toISOString(),
  };
}

/**
 * Convert FlowDesign to FlowTemplateCreate format for API
 */
export function convertDesignToTemplate(
  design: FlowDesign,
  options: {
    versionNumber: number;
    isDraft: boolean;
    isActive: boolean;
  }
): FlowTemplateCreate {
  // Convert FlowDesign nodes to FlowTemplateStep array
  const steps: FlowTemplateStep[] = design.nodes.map((node: FlowNode, index: number): FlowTemplateStep => {
    const messageType = node.type || 'text';
    const config = node.data.config || {};

    // Validate message type
    if (!VALID_MESSAGE_TYPES.includes(messageType)) {
      logger.warn(`Invalid message_type '${messageType}', defaulting to 'text'`);
    }

    return {
      step_number: index + 1,
      intent: node.data.label || 'unknown',
      ai_instructions: (config['aiInstructions'] as string) || '',
      message_type: VALID_MESSAGE_TYPES.includes(messageType) ? messageType : 'text',
      base_content: (config['content'] as string) || node.data.description || '',
      personalization_hints: (config['personalizationHints'] as string[]) || [],
    };
  });

  // Extract category from metadata
  const flowCategory = design.metadata?.category || 'custom_flow';

  return {
    kind_key: flowCategory,
    display_name: design.name || 'Novo Flow',
    description: design.description || '',
    version_number: options.versionNumber,
    steps,
    metadata: {
      flow_type: flowCategory,
      humanization_level: 'high',
      version: `${options.versionNumber}.0.0`,
    },
    is_active: options.isActive,
    is_draft: options.isDraft,
  };
}
