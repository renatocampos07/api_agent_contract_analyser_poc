import React from 'react';

export const UploadForm = ({ onFileChange, onRagChange, onSubmit, file, useRag }) => {
  return (
    <div className="upload-form">
      <div className="form-group">
        <label htmlFor="file-upload">1. Selecione seu arquivo .docx:</label>
        <input 
          id="file-upload"
          type="file" 
          accept=".docx"
          onChange={(e) => onFileChange(e.target.files[0])} 
        />
        {file && <p>Selecionado: {file.name}</p>}
      </div>

      <div className="form-group">
        <label htmlFor="rag-toggle">2. Opções de Análise:</label>
        <div className="toggle-group">
          <input 
            id="rag-toggle"
            type="checkbox" 
            checked={useRag}
            onChange={(e) => onRagChange(e.target.checked)}
            disabled // <-- RAG DESABILITADO NA v1.0
          />
          <label htmlFor="rag-toggle" className="disabled-label">
            Usar Manual de Referência (RAG) (v2.0)
          </label>
        </div>
      </div>

      <button onClick={onSubmit} disabled={!file} className="submit-btn">
        Analisar Documento
      </button>
    </div>
  );
};