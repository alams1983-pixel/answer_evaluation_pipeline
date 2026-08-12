export type SchemaFieldType = 'string' | 'number' | 'integer' | 'boolean' | 'array' | 'object';

export interface SchemaFieldConstraint {
  minLength?: number;
  maxLength?: number;
  minimum?: number;
  maximum?: number;
  enum?: string[];
}

export interface SchemaField {
  id: string;
  key: string;
  type: SchemaFieldType;
  required: boolean;
  description?: string;
  constraints: SchemaFieldConstraint;
  arrayItemType?: SchemaFieldType;
  children: SchemaField[];
}

let idCounter = 0;
function generateId(): string {
  idCounter++;
  return `field_${Date.now()}_${idCounter}`;
}

export function createEmptyField(overrides: Partial<SchemaField> = {}): SchemaField {
  return {
    id: generateId(),
    key: '',
    type: 'string',
    required: false,
    description: '',
    constraints: {},
    children: [],
    ...overrides,
  };
}

export function fieldsToJsonSchema(fields: SchemaField[]): object {
  const properties: Record<string, any> = {};
  const required: string[] = [];

  for (const field of fields) {
    if (!field.key) continue;

    const prop = fieldToJsonProperty(field);
    properties[field.key] = prop;

    if (field.required) {
      required.push(field.key);
    }
  }

  const schema: Record<string, any> = {
    type: 'object',
    properties,
  };

  if (required.length > 0) {
    schema.required = required;
  }

  return schema;
}

function fieldToJsonProperty(field: SchemaField): any {
  const result: Record<string, any> = {
    type: field.type,
  };

  if (field.description) {
    result.description = field.description;
  }

  if (field.type === 'string') {
    if (field.constraints.minLength !== undefined) result.minLength = field.constraints.minLength;
    if (field.constraints.maxLength !== undefined) result.maxLength = field.constraints.maxLength;
    if (field.constraints.enum && field.constraints.enum.length > 0) {
      result.enum = field.constraints.enum;
    }
  } else if (field.type === 'number' || field.type === 'integer') {
    if (field.constraints.minimum !== undefined) result.minimum = field.constraints.minimum;
    if (field.constraints.maximum !== undefined) result.maximum = field.constraints.maximum;
  } else if (field.type === 'object') {
    const childSchema = fieldsToJsonSchema(field.children) as Record<string, any>;
    result.properties = childSchema.properties;
    if (childSchema.required) result.required = childSchema.required;
  } else if (field.type === 'array') {
    if (field.arrayItemType === 'object') {
      const itemSchema = fieldsToJsonSchema(field.children);
      result.items = {
        type: 'object',
        ...itemSchema,
      };
    } else if (field.arrayItemType) {
      result.items = { type: field.arrayItemType };
    } else {
      result.items = { type: 'string' };
    }
  }

  return result;
}

export function jsonSchemaToFields(schema: any): SchemaField[] {
  if (!schema || schema.type !== 'object' || !schema.properties) {
    return [];
  }

  const fields: SchemaField[] = [];
  const requiredKeys = new Set(schema.required || []);

  for (const [key, propDef] of Object.entries(schema.properties)) {
    const field = jsonPropertyToField(key, propDef as any, requiredKeys.has(key));
    fields.push(field);
  }

  return fields;
}

function jsonPropertyToField(key: string, propDef: any, isRequired: boolean): SchemaField {
  const fieldType = propDef.type || 'string';

  const field: SchemaField = {
    id: generateId(),
    key,
    type: fieldType as SchemaFieldType,
    required: isRequired,
    description: propDef.description || '',
    constraints: {},
    children: [],
  };

  if (fieldType === 'string') {
    if (propDef.minLength !== undefined) field.constraints.minLength = propDef.minLength;
    if (propDef.maxLength !== undefined) field.constraints.maxLength = propDef.maxLength;
    if (propDef.enum) field.constraints.enum = propDef.enum;
  } else if (fieldType === 'number' || fieldType === 'integer') {
    if (propDef.minimum !== undefined) field.constraints.minimum = propDef.minimum;
    if (propDef.maximum !== undefined) field.constraints.maximum = propDef.maximum;
  } else if (fieldType === 'object') {
    field.children = jsonSchemaToFields(propDef);
  } else if (fieldType === 'array') {
    if (propDef.items) {
      if (propDef.items.type === 'object') {
        field.arrayItemType = 'object';
        field.children = jsonSchemaToFields(propDef.items);
      } else {
        field.arrayItemType = propDef.items.type as SchemaFieldType;
      }
    } else {
      field.arrayItemType = 'string';
    }
  }

  return field;
}

export const SAMPLE_SCHEMA_DEFINITION = {
  type: "object",
  required: ["student", "total_awarded", "total_max", "questions"],
  properties: {
    student: {
      type: "object",
      required: ["name", "roll_no", "class"],
      properties: {
        name: { type: "string", description: "Student full name" },
        roll_no: { type: "string", description: "Roll number" },
        class: { type: "string", description: "Class/section" }
      }
    },
    subject: { type: "string", description: "Subject name" },
    exam_title: { type: "string", description: "Exam title" },
    total_max: { type: "number", description: "Maximum possible marks" },
    total_awarded: { type: "number", description: "Marks awarded" },
    overall_feedback: { type: "string", description: "General feedback for the student" },
    questions: {
      type: "array",
      description: "Per-question evaluation",
      items: {
        type: "object",
        required: ["q_no", "awarded", "max"],
        properties: {
          q_no: { type: "string", description: "Question number/identifier" },
          awarded: { type: "number", minimum: 0, description: "Marks awarded" },
          max: { type: "number", minimum: 0, description: "Maximum marks for this question" },
          feedback: { type: "string", description: "Question-specific feedback" },
          page_refs: {
            type: "array",
            items: { type: "integer" },
            description: "Page numbers where this question appears"
          },
          confidence: {
            type: "number",
            minimum: 0,
            maximum: 1,
            description: "AI confidence score (0-1)"
          }
        }
      }
    }
  }
};
