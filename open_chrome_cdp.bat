@echo off
REM Abre um Chrome com CDP (porta 9222) usando um perfil dedicado.
REM Faça login no site nesta janela e mantenha-a aberta enquanto roda o scraper.

"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="%USERPROFILE%\chrome_tec_profile"
