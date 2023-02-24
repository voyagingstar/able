import { execSync, exec, spawn } from 'child_process'

var stt  

export function StartTranscription(port, argv) {
    console.log('start stt service')
    // if (argv.stt != 'OFF')
        // process.on('SIGINT', () => {
        //     // console.log(`SIGINT: kill STT Child Process `);
        //     // stt.stdin.pause();
        //     // stt.kill();
        //     process.abort()
        // });

    stt = spawn(`./whisper-mint/whisper/bin/python3`,
        [`./whisper-mint/main.py`, `${port}`],
        { detached: true });

    stt.stdout.on('data', (data) => {
        console.log(`STT stdout: ${data}`);
    });

    stt.stderr.on('data', (data) => {
        console.error(`STT stderr: ${data}`);
    });

    stt.on('close', (code) => {
        console.log(`stt process exited with code ${code}`);
    });
}

