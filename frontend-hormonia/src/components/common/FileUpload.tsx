import React, { useCallback, useState } from 'react'
import { Upload, X, FileText, Image, File } from 'lucide-react'
import { Card, CardContent } from '../ui/card'
import { Button } from '../ui/button'
import { Progress } from '../ui/progress'
import { useToast } from '@/hooks/use-toast'

interface FileUploadProps {
  accept?: string
  multiple?: boolean
  maxSize?: number // in MB
  onUpload: (files: File[]) => Promise<void>
  onRemove?: (index: number) => void
  disabled?: boolean
  className?: string
}

export const FileUpload: React.FC<FileUploadProps> = ({
  accept = '*',
  multiple = false,
  maxSize = 10,
  onUpload,
  onRemove,
  disabled = false,
  className = ''
}) => {
  const { toast } = useToast()
  const [files, setFiles] = useState<File[]>([])
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [dragActive, setDragActive] = useState(false)

  const validateFile = (file: File): boolean => {
    const maxSizeBytes = maxSize * 1024 * 1024

    if (file.size > maxSizeBytes) {
      toast({
        variant: 'destructive',
        title: 'File too large',
        description: `File "${file.name}" exceeds the maximum size of ${maxSize}MB`
      })
      return false
    }

    if (accept !== '*') {
      const acceptedTypes = accept.split(',').map(type => type.trim())
      const fileType = file.type || ''
      const fileExtension = `.${file.name.split('.').pop()}`

      const isAccepted = acceptedTypes.some(type =>
        type === fileType || type === fileExtension ||
        (type.endsWith('/*') && fileType.startsWith(type.replace('/*', '')))
      )

      if (!isAccepted) {
        toast({
          variant: 'destructive',
          title: 'Invalid file type',
          description: `File "${file.name}" is not an accepted file type`
        })
        return false
      }
    }

    return true
  }

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }, [])

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      e.stopPropagation()
      setDragActive(false)

      if (disabled || uploading) return

      const droppedFiles = Array.from(e.dataTransfer.files)
      const validFiles = droppedFiles.filter(validateFile)

      if (validFiles.length > 0) {
        const newFiles = multiple ? [...files, ...validFiles] : validFiles.slice(0, 1)
        setFiles(newFiles)
      }
    },
    [disabled, uploading, files, multiple]
  )

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (disabled || uploading) return

    const selectedFiles = e.target.files ? Array.from(e.target.files) : []
    const validFiles = selectedFiles.filter(validateFile)

    if (validFiles.length > 0) {
      const newFiles = multiple ? [...files, ...validFiles] : validFiles.slice(0, 1)
      setFiles(newFiles)
    }
  }

  const handleUpload = async () => {
    if (files.length === 0) {
      toast({
        variant: 'destructive',
        title: 'No files selected',
        description: 'Please select at least one file to upload'
      })
      return
    }

    setUploading(true)
    setUploadProgress(0)

    try {
      // Simulate progress (in real app, track actual upload progress)
      const progressInterval = setInterval(() => {
        setUploadProgress(prev => Math.min(prev + 10, 90))
      }, 200)

      await onUpload(files)

      clearInterval(progressInterval)
      setUploadProgress(100)

      toast({
        variant: 'success',
        title: 'Upload successful',
        description: `Successfully uploaded ${files.length} file(s)`
      })

      setFiles([])
      setUploadProgress(0)
    } catch (error) {
      toast({
        variant: 'destructive',
        title: 'Upload failed',
        description: error instanceof Error ? error.message : 'An error occurred during upload'
      })
    } finally {
      setUploading(false)
      setUploadProgress(0)
    }
  }

  const handleRemoveFile = (index: number) => {
    const newFiles = files.filter((_, i) => i !== index)
    setFiles(newFiles)
    if (onRemove) {
      onRemove(index)
    }
  }

  const getFileIcon = (file: File) => {
    if (file.type.startsWith('image/')) return <Image className="h-4 w-4" />
    if (file.type.startsWith('text/')) return <FileText className="h-4 w-4" />
    return <File className="h-4 w-4" />
  }

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  return (
    <div className={className}>
      <Card
        className={`border-2 border-dashed transition-colors ${
          dragActive ? 'border-primary bg-primary/5' : 'border-gray-300'
        } ${disabled || uploading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
      >
        <CardContent className="p-6">
          <input
            id="file-upload"
            type="file"
            className="hidden"
            accept={accept}
            multiple={multiple}
            onChange={handleFileSelect}
            disabled={disabled || uploading}
          />

          <label
            htmlFor="file-upload"
            className="flex flex-col items-center justify-center cursor-pointer"
          >
            <Upload className="h-10 w-10 text-gray-400 mb-3" />
            <p className="text-sm font-medium text-gray-700">
              Click to upload or drag and drop
            </p>
            <p className="text-xs text-gray-500 mt-1">
              {accept === '*' ? 'Any file type' : `Accepted: ${accept}`}
            </p>
            <p className="text-xs text-gray-500">
              Max size: {maxSize}MB {multiple && '• Multiple files allowed'}
            </p>
          </label>
        </CardContent>
      </Card>

      {files.length > 0 && (
        <div className="mt-4 space-y-2">
          {files.map((file, index) => (
            <Card key={index}>
              <CardContent className="p-3 flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  {getFileIcon(file)}
                  <div>
                    <p className="text-sm font-medium">{file.name}</p>
                    <p className="text-xs text-gray-500">{formatFileSize(file.size)}</p>
                  </div>
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => handleRemoveFile(index)}
                  disabled={uploading}
                >
                  <X className="h-4 w-4" />
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {uploading && (
        <div className="mt-4">
          <Progress value={uploadProgress} className="h-2" />
          <p className="text-xs text-gray-500 mt-1 text-center">
            Uploading... {uploadProgress}%
          </p>
        </div>
      )}

      {files.length > 0 && !uploading && (
        <Button
          className="mt-4 w-full"
          onClick={handleUpload}
          disabled={disabled}
        >
          Upload {files.length} file{files.length !== 1 ? 's' : ''}
        </Button>
      )}
    </div>
  )
}

export default FileUpload