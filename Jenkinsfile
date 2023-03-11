pipeline {
    agent any
    
    stages {
        stage('Undeploy') {
            steps {
                // Stop running microblog container (microblog label applied to microblog container by this repo's Dockerfile)
                sh 'docker stop $(docker ps -q --filter name=microblog) || true && docker rm $(docker ps -q --filter name=microblog) || true'
            }
        }
        stage('Build') {
            environment {
                TWILIO_CREDS = credentials('twilio-creds')
            }
            steps {
                sh 'chown -R root:jenkins'
                sh 'sudo cp $TWILIO_CREDS .env'
                sh 'docker build -t microblog:latest .'
            }
        }
        stage('Deploy') {
            steps {
                // Deploy new container
                sh 'docker run --name microblog -d -p 5000:5000 --rm microblog:latest'
                // Remove all images except for jenkins
                sh 'docker image prune -af --filter "label!=org.opencontainers.image.vendor=Jenkins project"'
            }
        }
        stage('Selenium Tests') {
            steps {
                echo 'Running Selenium Tests...'
                //sh 'python3 selenium.py'
            }
        }
    }
    
    // Post always runs even if the pipeline fails
    post {
        success {
            echo 'Pipeline has completed'
             discordSend description: '', footer: '', image: '', link: 'http://3.220.122.102:8080/', result: '', scmWebUrl: '', thumbnail: '', title: 
                'Pipeline has completed ✅', webhookURL: 'https://discord.com/api/webhooks/1075879011667955872/Nk0gmKZkrISEs-hru-HjtzzgezWweABCdPsOKGIzkmj5xMcqKC3m1-dx7GZSu0yURAOo'
        }
        failure {
            echo 'Something has failed!'
             discordSend description: 'Pipeline has failed!', footer: '', image: '', link: 'http://3.220.122.102:8080/', result: '', scmWebUrl: '', thumbnail: '', title: 
                'Pipeline failure ❌', webhookURL: 'https://discord.com/api/webhooks/1075879011667955872/Nk0gmKZkrISEs-hru-HjtzzgezWweABCdPsOKGIzkmj5xMcqKC3m1-dx7GZSu0yURAOo'
        }
    }
}
