import { TextDecoder, TextEncoder } from 'node:util'
import { ReadableStream, TransformStream, WritableStream } from 'node:stream/web'
import { Blob, File } from 'node:buffer'
import { BroadcastChannel, MessageChannel, MessagePort } from 'node:worker_threads'

const globalScope = globalThis as typeof globalThis & {
  TextDecoder?: typeof TextDecoder
  TextEncoder?: typeof TextEncoder
  ReadableStream?: typeof ReadableStream
  TransformStream?: typeof TransformStream
  WritableStream?: typeof WritableStream
  Blob?: typeof Blob
  File?: typeof File
  MessageChannel?: typeof MessageChannel
  MessagePort?: typeof MessagePort
  BroadcastChannel?: typeof BroadcastChannel
  fetch?: typeof globalThis.fetch
  Headers?: typeof globalThis.Headers
  FormData?: typeof globalThis.FormData
  Request?: typeof globalThis.Request
  Response?: typeof globalThis.Response
}

globalScope.TextDecoder ??= TextDecoder
globalScope.TextEncoder ??= TextEncoder
globalScope.ReadableStream ??= ReadableStream
globalScope.TransformStream ??= TransformStream
globalScope.WritableStream ??= WritableStream
globalScope.Blob ??= Blob
globalScope.File ??= File
globalScope.MessageChannel ??= MessageChannel
globalScope.MessagePort ??= MessagePort
globalScope.BroadcastChannel ??= BroadcastChannel

const { fetch, Headers, FormData, Request, Response } = require('undici')

globalScope.fetch ??= fetch
globalScope.Headers ??= Headers
globalScope.FormData ??= FormData
globalScope.Request ??= Request
globalScope.Response ??= Response
