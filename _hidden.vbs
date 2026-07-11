' AXData Studio 서버를 창 없이(백그라운드) 실행하는 도우미.
' start.bat 이 호출합니다. 세 번째 인자 0 = 숨김 창, False = 종료 대기 안 함.
Dim sh, fso, here
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
here = fso.GetParentFolderName(WScript.ScriptFullName)
sh.Run """" & here & "\_server.bat""", 0, False
