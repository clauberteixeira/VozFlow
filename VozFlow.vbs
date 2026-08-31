' Inicia o VozFlow sem nenhuma janela de console.
Set fso = CreateObject("Scripting.FileSystemObject")
raiz = fso.GetParentFolderName(WScript.ScriptFullName)

pyw = raiz & "\.venv\Scripts\pythonw.exe"
If Not fso.FileExists(pyw) Then
    MsgBox "Ambiente nao encontrado." & vbCrLf & vbCrLf & _
           "Rode o instalar.bat antes de usar o VozFlow.", 48, "VozFlow"
    WScript.Quit 1
End If

Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = raiz
sh.Run """" & pyw & """ """ & raiz & "\main.py""", 0, False
