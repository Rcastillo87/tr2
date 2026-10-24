@extends('layouts.app')
@section('title', $strategy->exists ? 'Editar Estrategia' : 'Nueva Estrategia')
@section('header', $strategy->exists ? 'Editar Estrategia' : 'Nueva Estrategia')

@section('content')
<style>button, a[href] { cursor: pointer; }</style>

<div class="mb-4">
    <a href="{{ route('strategies.index') }}" class="text-[11px]" style="color:var(--color-text-muted);">← Volver al gestor</a>
</div>

<form method="POST" action="{{ $strategy->exists ? route('strategies.update', $strategy) : route('strategies.store') }}" id="strategyForm">
    @csrf
    @if($strategy->exists) @method('PUT') @endif

    <div class="grid grid-cols-1 lg:grid-cols-[350px_1fr] gap-4 items-start">
        {{-- Panel Izquierdo: Metadatos --}}
        <div class="rounded-lg border p-4 space-y-4" style="background:var(--color-surface); border-color:var(--color-border-soft);">
            <div>
                <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Nombre de la Estrategia</label>
                <input type="text" name="name" value="{{ old('name', $strategy->name) }}" required
                       class="w-full rounded-lg px-3 py-2 text-sm border focus:outline-none"
                       style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                @error('name') <p class="text-[10px] mt-1" style="color:var(--color-loss);">{{ $message }}</p> @enderror
            </div>

            <div>
                <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Descripción</label>
                <input type="text" name="description" value="{{ old('description', $strategy->description) }}"
                       class="w-full rounded-lg px-3 py-2 text-sm border focus:outline-none"
                       style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
            </div>

            {{-- Método de carga del Código --}}
            <div class="border-t pt-4" style="border-color:var(--color-border-soft);">
                <label class="block text-[11px] mb-2" style="color:var(--color-text-muted);">Código Fuente (Python)</label>
                <div class="flex gap-2 mb-2">
                    <button type="button" onclick="switchTab('editor')" id="tab-btn-editor" class="flex-1 py-1.5 text-[11px] rounded border font-medium" style="background:var(--color-info); color:#fff; border-color:var(--color-info);">Escribir</button>
                    <button type="button" onclick="switchTab('upload')" id="tab-btn-upload" class="flex-1 py-1.5 text-[11px] rounded border" style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">Subir .py</button>
                </div>
                
                {{-- Input de subida (oculto por defecto) --}}
                <div id="upload-area" class="hidden mt-2">
                    <input type="file" id="fileInput" accept=".py" class="w-full text-[11px] text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-xs file:font-semibold file:bg-[#1E4A2E] file:text-[#3DD68C] hover:file:bg-[#2A6B42]" onchange="handleFileUpload(event)">
                    <p class="text-[10px] mt-1" style="color:var(--color-text-muted);">Sube tu archivo .py y se cargará en el editor.</p>
                </div>
            </div>
        </div>

        {{-- Panel Derecho: Editores --}}
        <div class="space-y-4">
            {{-- Editor de Código --}}
            <div id="editor-code-container" class="rounded-lg border overflow-hidden" style="background:var(--color-surface); border-color:var(--color-border-soft);">
                <div class="px-4 py-2 border-b flex justify-between items-center" style="border-color:var(--color-border-soft); background:var(--color-surface-raised);">
                    <span class="text-[11px] font-medium" style="color:var(--color-text-muted);">Editor de Código Python</span>
                </div>
                <div id="monacoCode" style="height: 400px; width: 100%;"></div>
            </div>

            {{-- Editor de Configuración (JSON) --}}
            <div class="rounded-lg border overflow-hidden" style="background:var(--color-surface); border-color:var(--color-border-soft);">
                <div class="px-4 py-2 border-b flex justify-between items-center" style="border-color:var(--color-border-soft); background:var(--color-surface-raised);">
                    <span class="text-[11px] font-medium" style="color:var(--color-text-muted);">Configuración de Parámetros (JSON)</span>
                    <span class="text-[10px]" style="color:var(--color-text-muted);">Estos son los valores por defecto</span>
                </div>
                <div id="monacoConfig" style="height: 200px; width: 100%;"></div>
            </div>

            <input type="hidden" name="code" id="codeInput" value="{{ old('code', $strategy->code) }}">
            <input type="hidden" name="config" id="configInput" value="{{ old('config', $strategy->config ? json_encode($strategy->config, JSON_PRETTY_PRINT) : '{}') }}">

            <button type="button" onclick="submitWithSmokeTest()" class="w-full text-sm font-medium px-4 py-3 rounded-lg"
                    style="background:var(--color-info); color:#fff;">
                💾 Guardar y Validar Estrategia
            </button>
        </div>
    </div>
</form>

@if ($errors->any())
    <div class="mt-4 rounded-lg border p-3 text-sm" style="background:#3A1A1C; border-color:#5A2226; color:var(--color-loss);">
        @foreach ($errors->all() as $error)
            <div>{{ $error }}</div>
        @endforeach
    </div>
@endif

@endsection

@push('scripts')
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.39.0/min/vs/loader.min.js"></script>
<script>
    let codeEditor, configEditor;

    require.config({ paths: { 'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.39.0/min/vs' }});
    
    require(['vs/editor/editor.main'], function() {
        // Editor de Código Python
        codeEditor = monaco.editor.create(document.getElementById('monacoCode'), {
            value: document.getElementById('codeInput').value,
            language: 'python',
            theme: 'vs-dark',
            minimap: { enabled: false },
            fontSize: 13,
            automaticLayout: true
        });
        codeEditor.onDidChangeModelContent(() => document.getElementById('codeInput').value = codeEditor.getValue());

        // Editor de Configuración JSON
        configEditor = monaco.editor.create(document.getElementById('monacoConfig'), {
            value: document.getElementById('configInput').value,
            language: 'json',
            theme: 'vs-dark',
            minimap: { enabled: false },
            fontSize: 13,
            automaticLayout: true
        });
        configEditor.onDidChangeModelContent(() => document.getElementById('configInput').value = configEditor.getValue());
    });

    function switchTab(tab) {
        const btnEditor = document.getElementById('tab-btn-editor');
        const btnUpload = document.getElementById('tab-btn-upload');
        const uploadArea = document.getElementById('upload-area');
        
        if (tab === 'editor') {
            btnEditor.style.background = 'var(--color-info)'; btnEditor.style.color = '#fff'; btnEditor.style.borderColor = 'var(--color-info)';
            btnUpload.style.background = 'var(--color-surface-raised)'; btnUpload.style.color = 'var(--color-text-primary)'; btnUpload.style.borderColor = 'var(--color-border-strong)';
            uploadArea.classList.add('hidden');
        } else {
            btnUpload.style.background = 'var(--color-info)'; btnUpload.style.color = '#fff'; btnUpload.style.borderColor = 'var(--color-info)';
            btnEditor.style.background = 'var(--color-surface-raised)'; btnEditor.style.color = 'var(--color-text-primary)'; btnEditor.style.borderColor = 'var(--color-border-strong)';
            uploadArea.classList.remove('hidden');
        }
    }

    function handleFileUpload(event) {
        const file = event.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = function(e) {
            const content = e.target.result;
            if (codeEditor) {
                codeEditor.setValue(content);
                document.getElementById('codeInput').value = content;
                switchTab('editor'); // Volver a la pestaña del editor para mostrar el código
                Swal.fire({title: 'Archivo cargado', text: 'El código .py se ha cargado en el editor.', icon: 'success', background: '#11161F', color: '#E5E9F0'});
            }
        };
        reader.readAsText(file);
    }

    function submitWithSmokeTest() {
        Swal.fire({
            title: 'Validando Estrategia...',
            html: 'Ejecutando Smoke Test. Comprobando sintaxis y apertura de operaciones...',
            allowOutsideClick: false,
            background: '#11161F', color: '#E5E9F0',
            didOpen: () => Swal.showLoading()
        });
        document.getElementById('strategyForm').submit();
    }
</script>
@endpush
