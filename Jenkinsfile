pipeline {
    agent any
    
    stages {
        stage('Build') {
            steps {
                sh 'docker build -t microblog:latest .'   
            }
        }
        stage("Hello To Discord") {
            steps {
                echo ' Test to Discord'
                discordSend description: '', footer: '', image: '', link: 'http://3.91.14.163:8080', result: '', scmWebUrl: '', thumbnail: '', title: 
                'HelloToDiscordTest', webhookURL: 'https://discord.com/api/webhooks/1075879011667955872/Nk0gmKZkrISEs-hru-HjtzzgezWweABCdPsOKGIzkmj5xMcqKC3m1-dx7GZSu0yURAOo'
            }
        }
    }
}
