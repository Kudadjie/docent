import { describe, it, expect } from 'vitest';
import {
  resolveField, resolveFields, initialValues, isComplete, buildPayload,
} from '../app/tools/_schema-form';

const req = (...names: string[]) => new Set(names);

describe('resolveField', () => {
  it('classifies a plain required string', () => {
    const f = resolveField('topic', { type: 'string', title: 'Topic' }, req('topic'));
    expect(f.kind).toBe('string');
    expect(f.required).toBe(true);
    expect(f.nullable).toBe(false);
  });

  it('detects an enum and pulls its values', () => {
    const f = resolveField('backend', { type: 'string', enum: ['free', 'feynman'], default: 'feynman' }, req());
    expect(f.kind).toBe('enum');
    expect(f.enumValues).toEqual(['free', 'feynman']);
    expect(f.default).toBe('feynman');
  });

  it('unwraps anyOf[T, null] to the non-null branch and flags nullable', () => {
    const f = resolveField('deadline', {
      anyOf: [{ type: 'string' }, { type: 'null' }], default: null,
    }, req());
    expect(f.kind).toBe('string');
    expect(f.nullable).toBe(true);
    expect(f.required).toBe(false);
  });

  it('unwraps a nullable enum', () => {
    const f = resolveField('status', {
      anyOf: [{ enum: ['queued', 'done'], type: 'string' }, { type: 'null' }], default: null,
    }, req());
    expect(f.kind).toBe('enum');
    expect(f.enumValues).toEqual(['queued', 'done']);
    expect(f.nullable).toBe(true);
  });

  it('classifies integer, boolean, and string arrays', () => {
    expect(resolveField('n', { type: 'integer', default: 20 }, req()).kind).toBe('integer');
    expect(resolveField('flag', { type: 'boolean', default: false }, req()).kind).toBe('boolean');
    expect(resolveField('files', { type: 'array', items: { type: 'string' } }, req()).kind).toBe('string_array');
  });

  it('falls back to json for nested objects', () => {
    expect(resolveField('cfg', { type: 'object' }, req()).kind).toBe('json');
  });
});

describe('initialValues', () => {
  it('seeds defaults per kind', () => {
    const fields = resolveFields({
      properties: {
        topic: { type: 'string' },
        n: { type: 'integer', default: 20 },
        flag: { type: 'boolean', default: true },
        files: { type: 'array', items: { type: 'string' } },
      },
      required: ['topic'],
    });
    const v = initialValues(fields);
    expect(v.topic).toBe('');
    expect(v.n).toBe('20');
    expect(v.flag).toBe(true);
    expect(v.files).toEqual([]);
  });
});

describe('isComplete', () => {
  const fields = resolveFields({
    properties: { topic: { type: 'string' }, n: { type: 'integer', default: 5 } },
    required: ['topic'],
  });

  it('is false when a required field is blank', () => {
    expect(isComplete(fields, { topic: '', n: '5' })).toBe(false);
  });

  it('is true once required fields are filled', () => {
    expect(isComplete(fields, { topic: 'storm surge', n: '5' })).toBe(true);
  });
});

describe('buildPayload', () => {
  const fields = resolveFields({
    properties: {
      topic: { type: 'string' },
      backend: { type: 'string', enum: ['free', 'feynman'], default: 'feynman' },
      n: { type: 'integer', default: 20 },
      flag: { type: 'boolean', default: false },
      files: { type: 'array', items: { type: 'string' } },
      notes: { anyOf: [{ type: 'string' }, { type: 'null' }], default: null },
    },
    required: ['topic'],
  });

  it('omits empty optionals so action defaults apply, and coerces numbers', () => {
    const payload = buildPayload(fields, {
      topic: 'coastal flooding', backend: 'free', n: '12', flag: true, files: [], notes: '',
    });
    expect(payload).toEqual({ topic: 'coastal flooding', backend: 'free', n: 12, flag: true });
    expect(payload).not.toHaveProperty('notes');
    expect(payload).not.toHaveProperty('files');
  });

  it('includes non-empty arrays', () => {
    const payload = buildPayload(fields, { topic: 'x', files: ['a.md', 'b.pdf'] });
    expect(payload.files).toEqual(['a.md', 'b.pdf']);
  });

  it('throws a clear error on malformed json fields', () => {
    const jsonFields = resolveFields({ properties: { cfg: { type: 'object' } } });
    expect(() => buildPayload(jsonFields, { cfg: '{ bad' })).toThrow(/not valid JSON/);
  });
});
