#ifndef Payload
  #error Payload directory is required
#endif
#ifndef ReleaseOutput
  #error ReleaseOutput directory is required
#endif
#ifndef StarterData
  #error StarterData directory is required
#endif
#ifdef InstallSelfTest
  #define ApplicationId "{{E189C77E-1CE7-4B4C-9AE5-88563EC10F54}"
  #define UninstallKey "{E189C77E-1CE7-4B4C-9AE5-88563EC10F54}_is1"
  #define ProductName "原境扫描器安装自检"
  #define SetupFilename "DomainScanner_Setup_SelfTest"
#else
  #define ApplicationId "{{9BFFEB07-50E4-4C84-8DCB-E13F34427D43}"
  #define UninstallKey "{9BFFEB07-50E4-4C84-8DCB-E13F34427D43}_is1"
  #define ProductName "原神副本扫描器"
  #define SetupFilename "DomainScanner_Setup_0.3.0-preview.9"
#endif

[Setup]
AppId={#ApplicationId}
AppName={#ProductName}
AppVersion=0.3.0-preview.9
AppVerName={#ProductName} 0.3.0 预览版9
DefaultDirName={autopf}\DomainScanner
DefaultGroupName={#ProductName}
AppendDefaultDirName=yes
DisableDirPage=no
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.19041
OutputDir={#ReleaseOutput}
OutputBaseFilename={#SetupFilename}
UninstallDisplayIcon={app}\DomainScanner.exe
UninstallFilesDir={app}\_卸载\{code:UninstallGeneration}
Compression=lzma2/fast
SolidCompression=yes
LZMANumBlockThreads=2
WizardStyle=modern
CloseApplications=no
RestartApplications=no
SetupLogging=yes
UsePreviousAppDir=yes
AllowCancelDuringInstall=no

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: desktopicon; Description: "创建桌面快捷方式"; Flags: unchecked

[Files]
Source: "{#Payload}\DomainScanner.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Payload}\_运行依赖\*"; DestDir: "{app}\_运行依赖"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#Payload}\使用说明.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#StarterData}\learning\*.sqlite3"; DestDir: "{app}\缓存\详情模板实验\natural\default"; Flags: onlyifdoesntexist uninsneveruninstall; Check: ShouldSeedLearning
Source: "{#StarterData}\layout\1920x1080\*.json"; DestDir: "{app}\缓存\画面定位\1920x1080"; Flags: onlyifdoesntexist uninsneveruninstall; Check: ShouldSeedLayout
Source: "{#StarterData}\manifest.json"; DestDir: "{app}\缓存"; DestName: "预置资料说明.json"; Flags: onlyifdoesntexist uninsneveruninstall

[Icons]
Name: "{autoprograms}\{#ProductName}"; Filename: "{app}\DomainScanner.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\{#ProductName}"; Filename: "{app}\DomainScanner.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Code]
var
  SeedLearning: Boolean;
  SeedLayout: Boolean;
  PreviousDir: String;
  PreviousUninstaller: String;
  PreviousRemoved: Boolean;
  DataPage: TInputOptionWizardPage;
  PurgeData: Boolean;
  PurgeAuthorizedDir: String;
  SafeUninstallRoot: Boolean;
  UninstallToken: String;
  RemovePreviousButton: TNewButton;
  InstallMutationLocked: Boolean;

function OpenProcess(Access: LongWord; Inherit: Boolean; PID: LongWord): THandle;
  external 'OpenProcess@kernel32.dll stdcall';
function WaitForSingleObject(Handle: THandle; Milliseconds: LongWord): LongWord;
  external 'WaitForSingleObject@kernel32.dll stdcall';
function CloseHandle(Handle: THandle): Boolean;
  external 'CloseHandle@kernel32.dll stdcall';

function UninstallGeneration(Param: String): String;
begin
  if UninstallToken = '' then
    UninstallToken := Copy(GetSHA256OfString(ExpandConstant('{tmp}')), 1, 24);
  Result := UninstallToken;
end;

function OwnedUninstaller(const Folder, Executable: String): Boolean;
var Parent, Prefix, Token: String;
    I: Integer;
begin
  Parent := RemoveBackslashUnlessRoot(ExtractFileDir(Executable));
  Result := CompareText(Parent, Folder) = 0;
  if Result then exit;
  Prefix := AddBackslash(Folder) + '_卸载\';
  Result := Pos(Lowercase(Prefix), Lowercase(Parent)) = 1;
  if not Result then exit;
  Token := Copy(Parent, Length(Prefix) + 1, Length(Parent));
  Result := Length(Token) = 24;
  if not Result then exit;
  for I := 1 to Length(Token) do
    if Pos(Token[I], '0123456789abcdef') = 0 then begin Result := False; exit; end;
end;

function ShouldSeedLearning: Boolean;
begin
  Result := SeedLearning;
end;

function ShouldSeedLayout: Boolean;
begin
  Result := SeedLayout;
end;

function DedicatedDirectory(const Value: String): String;
begin
  Result := RemoveBackslashUnlessRoot(ExpandFileName(Value));
  if CompareText(ExtractFileName(Result), 'DomainScanner') <> 0 then
    Result := AddBackslash(Result) + 'DomainScanner';
end;

function AppFolderSafe(const Value: String): Boolean;
var P: String;
begin
  P := RemoveBackslashUnlessRoot(ExpandFileName(Value));
  Result := (Length(P) > 14) and (CompareText(ExtractFileName(P), 'DomainScanner') = 0) and
    (CompareText(P, RemoveBackslashUnlessRoot(ExpandConstant('{app}'))) = 0);
end;

function AppRunningAt(const Folder: String): Boolean;
var Locator, Service, Processes, ProcessItem, PathValue: Variant;
    I: Integer;
    Prefix: String;
begin
  Result := False;
  Prefix := Lowercase(AddBackslash(Folder));
  try
    Locator := CreateOleObject('WbemScripting.SWbemLocator');
    Service := Locator.ConnectServer('', 'root\CIMV2');
    Processes := Service.ExecQuery('SELECT ExecutablePath FROM Win32_Process WHERE Name="DomainScanner.exe" OR Name="NativeDesktopHost.exe" OR Name="OverlayWindow.exe"');
    for I := 0 to Processes.Count - 1 do begin
      ProcessItem := Processes.ItemIndex(I);
      PathValue := ProcessItem.ExecutablePath;
      if not VarIsNull(PathValue) then
        if Pos(Prefix, Lowercase(String(PathValue))) = 1 then begin
          Result := True; exit;
        end;
    end;
  except
    Log('Unable to verify scanner process state: ' + GetExceptionMessage);
    Result := True;
  end;
end;

function AppRunning: Boolean;
begin
  Result := AppRunningAt(ExpandConstant('{app}'));
end;

procedure ReadPrevious;
var Key, P, U: String;
    Hive: Integer;
begin
  Key := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#UninstallKey}';
  Hive := HKLM;
  if not RegKeyExists(Hive, Key) then Hive := HKCU;
  if RegQueryStringValue(Hive, Key, 'InstallLocation', P) and
     RegQueryStringValue(Hive, Key, 'UninstallString', U) then begin
    P := RemoveBackslashUnlessRoot(ExpandFileName(P));
    if (Length(U) > 2) and (U[1] = '"') and (U[Length(U)] = '"') then
      U := Copy(U, 2, Length(U) - 2);
    if OwnedUninstaller(P, U) and
       (CompareText(ExtractFileName(P), 'DomainScanner') = 0) and
       (CompareText(Copy(ExtractFileName(U), 1, 5), 'unins') = 0) and FileExists(U) then begin
      PreviousDir := P;
      PreviousUninstaller := U;
    end else
      RaiseException('已有安装记录不完整，请先从系统应用列表卸载旧版。');
  end;
end;

function ChooseUninstallData(const Instruction, Folder: String): Integer;
var Choice: Integer;
begin
  { TaskDialog's first action is the default. Keep data first, then normalize
    its result to the existing IDNO=keep / IDYES=delete routing. }
  Choice := TaskDialogMsgBox(Instruction,
    '安装目录：' + #13#10 + Folder + #13#10 +
    '外部指定的工作簿始终保留。保留的旧数据不会自动迁移。',
    mbConfirmation, MB_YESNOCANCEL, ['仅卸载程序' + #10 + '保留设置、工作簿、产出和学习缓存（默认）',
     '卸载程序及全部数据' + #10 + '删除此安装目录内的设置、工作簿、产出和学习缓存',
     '取消'], 0);
  case Choice of
    IDYES: Result := IDNO;
    IDNO: Result := IDYES;
  else
    Result := IDCANCEL;
  end;
end;

procedure RemovePreviousClick(Sender: TObject);
var
  ExitCode, Choice: Integer;
  DeleteOldData: Boolean;
begin
  Choice := ChooseUninstallData('卸载旧版并更换安装位置', PreviousDir);
  if Choice = IDCANCEL then Exit;
  DeleteOldData := Choice = IDYES;
  if DeleteOldData and (((Length(PreviousDir) <= 14) or
    (CompareText(ExtractFileName(RemoveBackslashUnlessRoot(PreviousDir)), 'DomainScanner') <> 0) or
    (not OwnedUninstaller(PreviousDir, PreviousUninstaller))) or
    (Pos(Lowercase(AddBackslash(PreviousDir)), Lowercase(ExpandConstant('{srcexe}'))) = 1)) then begin
    MsgBox('不能安全清除该目录，或安装包正在旧目录内运行。请将安装包移到目录外后重试。', mbError, MB_OK); Exit;
  end;
  if AppRunningAt(PreviousDir) then begin
    MsgBox('扫描器或浮窗仍在运行，请退出后重试。', mbError, MB_OK); Exit;
  end;
  if not Exec(PreviousUninstaller, '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /UPGRADE=1 /DATA=keep', PreviousDir, SW_HIDE, ewWaitUntilTerminated, ExitCode) then begin
    MsgBox('无法启动旧版卸载程序。', mbError, MB_OK); Exit;
  end;
  if (ExitCode <> 0) or FileExists(AddBackslash(PreviousDir) + 'DomainScanner.exe') then begin
    MsgBox('旧版尚未卸载完成，安装位置仍保持原目录。', mbInformation, MB_OK); Exit;
  end;
  if DeleteOldData then begin
    if not DelTree(PreviousDir, True, True, True) then begin
      MsgBox('程序已卸载，但旧数据未能全部清除，请检查目录占用：' + #13#10 + PreviousDir,
        mbError, MB_OK);
    end;
  end;
  PreviousDir := '';
  PurgeData := False;
  PurgeAuthorizedDir := '';
  DataPage.SelectedValueIndex := 0;
  PreviousUninstaller := '';
  PreviousRemoved := False;
  WizardForm.DirEdit.Enabled := True;
  WizardForm.DirBrowseButton.Enabled := True;
  RemovePreviousButton.Visible := False;
  WizardForm.SelectDirLabel.Caption := '旧版已卸载。现在可以浏览并选择新的安装位置；旧数据不会自动迁移。';
  WizardForm.SelectDirBrowseLabel.Caption := '点击“浏览”选择安装位置，再点击“下一步”。';
end;

procedure InitializeWizard;
begin
  WizardForm.ReadyLabel.Caption := '请确认安装位置和数据选项。点击“安装”后，安装过程中不能取消。';
  ReadPrevious;
  if PreviousDir <> '' then begin
    WizardForm.DirEdit.Text := PreviousDir;
    WizardForm.DirEdit.Enabled := False;
    WizardForm.DirBrowseButton.Enabled := False;
    WizardForm.SelectDirLabel.Caption := '检测到已有安装，将在原位置替换程序。下一步可选择保留或清除扫描器数据。';
    WizardForm.SelectDirBrowseLabel.Caption := '继续将在原目录覆盖。若要更换位置，请先点击下面的卸载按钮。';
    RemovePreviousButton := TNewButton.Create(WizardForm);
    RemovePreviousButton.Parent := WizardForm.SelectDirPage;
    RemovePreviousButton.SetBounds(WizardForm.DirEdit.Left, WizardForm.DirEdit.Top + WizardForm.DirEdit.Height + ScaleY(16), ScaleX(190), ScaleY(25));
    RemovePreviousButton.Caption := '卸载旧版并选择其他位置';
    RemovePreviousButton.OnClick := @RemovePreviousClick;
  end else begin
    WizardForm.DirEdit.Text := DedicatedDirectory(WizardForm.DirEdit.Text);
    WizardForm.SelectDirLabel.Caption := '请选择安装位置。程序会放入独立的 DomainScanner 文件夹，产出与缓存集中保存在该文件夹中。';
  end;
  DataPage := CreateInputOptionPage(wpSelectDir, '安装与数据', '默认保留设置、工作簿、产出和学习缓存',
    '清除数据只影响安装目录内的内容，不会删除外部指定的工作簿。', True, False);
  DataPage.Add('保留已有数据，替换程序（推荐）');
  DataPage.Add('清除安装目录内的全部旧数据，重新安装');
  DataPage.SelectedValueIndex := 0;
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := (PageID = DataPage.ID) and (PreviousDir = '') and
    not DirExists(ExpandConstant('{app}\产出')) and not DirExists(ExpandConstant('{app}\缓存'));
end;

procedure SetInstallMutationLocked(Value: Boolean);
begin
  InstallMutationLocked := Value;
  WizardForm.CancelButton.Enabled := not Value;
end;

procedure CancelButtonClick(CurPageID: Integer; var Cancel, Confirm: Boolean);
begin
  if InstallMutationLocked then begin
    Cancel := False;
    Confirm := False;
    Log('Cancellation ignored while replacing the scanner program.');
  end;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpFinished then SetInstallMutationLocked(False)
  else if InstallMutationLocked then WizardForm.CancelButton.Enabled := False;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = wpSelectDir then begin
    PurgeData := False;
    PurgeAuthorizedDir := '';
    DataPage.SelectedValueIndex := 0;
    if PreviousDir <> '' then WizardForm.DirEdit.Text := PreviousDir
    else WizardForm.DirEdit.Text := DedicatedDirectory(WizardForm.DirEdit.Text);
  end;
  if CurPageID = DataPage.ID then begin
    PurgeAuthorizedDir := '';
    PurgeData := DataPage.SelectedValueIndex = 1;
    if PurgeData and not WizardSilent then
      Result := MsgBox('将删除此目录内的全部旧数据：' + #13#10 + ExpandConstant('{app}') + #13#10 +
        '包括设置、工作簿、JSON、截图、日志和学习缓存。此操作无法撤销。是否继续？',
        mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES;
    if PurgeData and Result then
      PurgeAuthorizedDir := RemoveBackslashUnlessRoot(ExpandFileName(WizardDirValue));
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var ExitCode: Integer;
    Prepared: Boolean;
begin
  Result := '';
  if PreviousDir <> '' then WizardForm.DirEdit.Text := PreviousDir;
  if not AppFolderSafe(ExpandConstant('{app}')) then begin
    Result := '安装位置不满足独立 DomainScanner 目录要求。'; exit;
  end;
  if AppRunning then begin
    Result := '扫描器或浮窗仍在运行，请先退出后重试；尚未卸载旧程序或清除数据。'; exit;
  end;
  if WizardSilent then PurgeData := CompareText(ExpandConstant('{param:DATA|keep}'), 'delete') = 0;
  if PurgeData and not WizardSilent then
    if CompareText(PurgeAuthorizedDir, RemoveBackslashUnlessRoot(ExpandFileName(ExpandConstant('{app}')))) <> 0 then begin
      Result := '安装位置已变化，请返回重新确认此目录的数据清除选择。尚未卸载或删除数据。'; exit;
    end;
  if PurgeData and (Pos(Lowercase(AddBackslash(ExpandConstant('{app}'))), Lowercase(ExpandConstant('{srcexe}'))) = 1) then begin
    Result := '安装包位于待清理目录中，请先将安装包移到此目录外，再选择清除数据重装。尚未移除旧程序或数据。'; exit;
  end;
  Prepared := False;
  SetInstallMutationLocked(True);
  try
  if (PreviousUninstaller <> '') and not PreviousRemoved then begin
    if not Exec(PreviousUninstaller, '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /UPGRADE=1 /DATA=keep',
      PreviousDir, SW_HIDE, ewWaitUntilTerminated, ExitCode) or (ExitCode <> 0) then begin
      Result := '旧版卸载未完成，请关闭扫描器后重试；未清除用户数据。'; exit;
    end;
    if FileExists(AddBackslash(PreviousDir) + 'DomainScanner.exe') then begin
      Result := '旧程序仍在运行或文件被占用，请关闭后重试。'; exit;
    end;
    if DirExists(ExpandConstant('{app}\_运行依赖')) then
      if not DelTree(ExpandConstant('{app}\_运行依赖'), True, True, True) then begin
        Result := '旧运行依赖仍被占用，请关闭扫描器后重试。'; exit;
      end;
    PreviousRemoved := True;
  end else if (PreviousDir = '') and FileExists(ExpandConstant('{app}\DomainScanner.exe')) then begin
    Result := '此目录已有未登记的程序，请选择其他位置，避免覆盖未知文件。'; exit;
  end;
  if PurgeData then begin
    if not DelTree(ExpandConstant('{app}'), True, True, True) then begin
      Result := '旧数据未能全部清除，请关闭占用文件的程序后重试。'; exit;
    end;
  end;
  SeedLearning := not DirExists(ExpandConstant('{app}\缓存\详情模板实验\natural\default'));
  SeedLayout := not DirExists(ExpandConstant('{app}\缓存\画面定位\1920x1080'));
  Prepared := True;
  finally
    if not Prepared then SetInstallMutationLocked(False);
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    SaveStringToFile(ExpandConstant('{app}\安装标识.txt'),
      'DomainScanner|{#UninstallKey}|' + GetSHA256OfString(Lowercase(RemoveBackslashUnlessRoot(ExpandConstant('{app}')))), False);
end;

function InitializeUninstall: Boolean;
var PID, Choice: Integer;
    Process: THandle;
    Marker: AnsiString;
begin
  Result := True;
  PID := StrToIntDef(ExpandConstant('{param:WAITPID|0}'), 0);
  if PID > 0 then begin
    Process := OpenProcess($00100000, False, PID);
    if Process <> 0 then begin
      if WaitForSingleObject(Process, 30000) <> 0 then begin
        CloseHandle(Process);
        MsgBox('扫描器尚未退出，卸载已取消。请关闭后重试。', mbError, MB_OK);
        Result := False; exit;
      end;
      CloseHandle(Process);
    end;
  end;
  if AppRunning then begin
    MsgBox('扫描器或浮窗仍在运行，请退出后重试。', mbError, MB_OK);
    Result := False; exit;
  end;
  SafeUninstallRoot := AppFolderSafe(ExpandConstant('{app}')) and
    LoadStringFromFile(ExpandConstant('{app}\安装标识.txt'), Marker);
  if SafeUninstallRoot then SafeUninstallRoot :=
    String(Marker) = 'DomainScanner|{#UninstallKey}|' + GetSHA256OfString(Lowercase(RemoveBackslashUnlessRoot(ExpandConstant('{app}'))));
  PurgeData := False;
  if CompareText(ExpandConstant('{param:UPGRADE|0}'), '1') = 0 then exit;
  if UninstallSilent then
    PurgeData := CompareText(ExpandConstant('{param:DATA|keep}'), 'delete') = 0
  else begin
    Choice := ChooseUninstallData('卸载原神副本扫描器', ExpandConstant('{app}'));
    if Choice = IDCANCEL then Result := False;
    PurgeData := Choice = IDYES;
  end;
  Log('DATA choice: purge=' + IntToStr(Ord(PurgeData)) + ', safe=' + IntToStr(Ord(SafeUninstallRoot)) + ', data=' + ExpandConstant('{param:DATA|keep}') + ', upgrade=' + ExpandConstant('{param:UPGRADE|0}'));
  if PurgeData and not SafeUninstallRoot then begin
    MsgBox('安装目录标识无效，已拒绝清除数据；请仅卸载程序。', mbError, MB_OK);
    Result := False;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  Log('UNINSTALL step=' + IntToStr(Ord(CurUninstallStep)) + ', purge=' + IntToStr(Ord(PurgeData)) + ', safe=' + IntToStr(Ord(SafeUninstallRoot)));
  if (CurUninstallStep = usPostUninstall) and PurgeData and SafeUninstallRoot then
    if not DelTree(ExpandConstant('{app}'), True, True, True) then
      RaiseException('程序已卸载，但部分数据被占用，未能全部清除：' + ExpandConstant('{app}'));
end;
