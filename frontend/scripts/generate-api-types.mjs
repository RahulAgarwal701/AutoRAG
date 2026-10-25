import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const document = JSON.parse(await readFile(resolve(root, "openapi.json"), "utf8"));

function identifier(value) {
  return /^[A-Za-z_$][\w$]*$/.test(value) ? value : JSON.stringify(value);
}

function schemaType(schema = {}) {
  if (schema.$ref) {
    return `components["schemas"][${JSON.stringify(schema.$ref.split("/").at(-1))}]`;
  }
  if (Object.hasOwn(schema, "const")) return JSON.stringify(schema.const);
  if (schema.anyOf) return schema.anyOf.map(schemaType).join(" | ");
  if (schema.oneOf) return schema.oneOf.map(schemaType).join(" | ");
  if (schema.enum) return schema.enum.map((value) => JSON.stringify(value)).join(" | ");
  if (schema.type === "array") return `Array<${schemaType(schema.items)}> `;
  if (schema.type === "object" || schema.properties) {
    const required = new Set(schema.required ?? []);
    const entries = Object.entries(schema.properties ?? {}).map(
      ([key, value]) => `${identifier(key)}${required.has(key) ? "" : "?"}: ${schemaType(value)};`,
    );
    if (schema.additionalProperties) {
      entries.push(`[key: string]: ${schemaType(schema.additionalProperties)};`);
    }
    return `{ ${entries.join(" ")} }`;
  }
  if (schema.type === "integer" || schema.type === "number") return "number";
  if (schema.type === "boolean") return "boolean";
  if (schema.type === "string") return "string";
  if (schema.type === "null") return "null";
  return "unknown";
}

const schemas = Object.entries(document.components?.schemas ?? {})
  .map(([name, schema]) => `    ${identifier(name)}: ${schemaType(schema)};`)
  .join("\n");

const output = `/* eslint-disable */
// Generated from openapi.json. Run: npm run generate:api
export interface components {
  schemas: {
${schemas}
  };
}
`;

const target = resolve(root, "lib/api/schema.ts");
await mkdir(dirname(target), { recursive: true });
await writeFile(target, output);
console.log(`Generated ${target}`);
