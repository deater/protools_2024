/*
 *	wattsup-fancy - Program for controlling the Watts Up? Pro Device
 *
 *	Based on code example by Patrick Mochel
 *
 * Print time followed by Watts, once per second
 * 	also log temperature and cpu-frequency.  this is not generic,
 *	currently hard-coded for a orange-pi 800
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>
#include <fcntl.h>
#include <termios.h>
#include <ctype.h>
#include <time.h>

#include <sys/stat.h>
#include <sys/time.h>

#include <signal.h>

static int debug=1;

static int done_running=0;
static int missed_samples=0;

static void ctrlc_handler(int sig, siginfo_t *foo, void *bar) {

	done_running=1;
}

/* start the external logging of power info */
/* #L,W,3,E,<Reserved>,<Interval>; */
static int wu_start_external_log(int wu_fd, int interval) {

	char command[BUFSIZ];
	int ret,length;

	if (debug) fprintf(stderr,"Enabling logging...\n");

	sprintf(command,"#L,W,3,E,1,%d;",interval);
	if (debug) fprintf(stderr,"%s\n",command);

	length=strlen(command);

	ret=write(wu_fd,command,length);
	if (ret!=length) {
		fprintf(stderr,"Error starting logging %s!\n",
			strerror(errno));
		return -1;
	}

	sleep(1);

	return 0;
}


/* stop the external logging of power info */
/* This is not in the documentation? */
/* #L,R,0; */
static int wu_stop_external_log(int wu_fd) {

	char command[BUFSIZ];
	int ret,length;

	if (debug) fprintf(stderr,"Disabling logging...\n");

	sprintf(command,"#L,R,0;");
	if (debug) fprintf(stderr,"%s\n",command);

	length=strlen(command);

	ret=write(wu_fd,command,length);
	if (ret!=length) {
		fprintf(stderr,"Error stopping logging %s!\n",
			strerror(errno));
		return -1;
	}

	sleep(1);

	return 0;
}


/* Open our device, probably ttyUSB0 */
static int open_device(char *device_name) {

	struct stat s;
	int ret;
	char full_device_name[BUFSIZ+6];

	snprintf(full_device_name,BUFSIZ+6,"/dev/%s",device_name);

	ret = stat(full_device_name, &s);
	if (ret < 0) {
		fprintf(stderr,"Problem statting %s, %s\n",
			full_device_name,strerror(errno));
		return -1;
	}

	if (!S_ISCHR(s.st_mode)) {
		fprintf(stderr,"Error: %s is not a TTY character device.",
			full_device_name);
		return -1;
	}

	ret = access(full_device_name, R_OK | W_OK);
	if (ret) {
		fprintf(stderr,"Error: %s is not writable, %s.",
			full_device_name,strerror(errno));
		return -1;
	}

	/* Not NONBLOCK */
	ret = open(full_device_name, O_RDWR);
	if (ret < 0) {
		fprintf(stderr,"Error! Could not open %s, %s",
			full_device_name, strerror(errno));
		return -1;
	}

	return ret;
}


/* Do the annoying Linux serial setup */
static int setup_serial_device(int fd) {

	struct termios t;
	int ret;

	/* get the current attributes */
	ret = tcgetattr(fd, &t);
	if (ret) {
		fprintf(stderr,"tcgetattr failed, %s\n",strerror(errno));
		return ret;
	}

	/* set terminal to "raw" mode */
	cfmakeraw(&t);

	/* set input speed to 115200 */
	/* (original code did B9600 ??? */
	cfsetispeed(&t, B115200);

	/* set output speed to 115200 */
	cfsetospeed(&t, B115200);

	/* discard any data received but not read */
	tcflush(fd, TCIFLUSH);

	/* 8N1 */
	t.c_cflag &= ~PARENB;
	t.c_cflag &= ~CSTOPB;
	t.c_cflag &= ~CSIZE;
	t.c_cflag |= CS8;

	/* set the new attributes */
	ret = tcsetattr(fd, TCSANOW, &t);

	if (ret) {
		fprintf(stderr,"ERROR: setting terminal attributes, %s\n",
			strerror(errno));
		return ret;
	}

	return 0;
}

/* Read from the meter */
static int wu_read(int fd) {

	int ret=-1;
	int offset=0;

	struct timeval sample_time;
	double double_time=0.0;
	double prev_time=0.0;

#define STRING_SIZE 256
	char string[STRING_SIZE];

	memset(string,0,STRING_SIZE);

	while(ret<0) {
		ret = read(fd, string, STRING_SIZE);
		if ((ret<0) && (ret!=EAGAIN)) {
			fprintf(stderr,"error reading from device %s\n",
				strerror(errno));
		}
	}

	if (string[0]!='#') {
		fprintf(stderr,"Protocol error with string %s\n",string);
		return ret;
	}

	prev_time=double_time;

	gettimeofday(&sample_time,NULL);
	double_time=(double)sample_time.tv_sec+
		((double)sample_time.tv_usec)/1000000.0;

	if ((double_time-prev_time>1.2) && (prev_time!=0.0)) {
		fprintf(stderr,"Error!  More than 1s between times!\n");
		missed_samples++;
	}


	offset=ret;

	/* Typically ends in ;\r\n */
	while(string[offset-1]!='\n') {
//		printf("Offset is %d char %d\n",offset,string[offset-1]);
		ret = read(fd, string+offset, STRING_SIZE-ret);
		offset+=ret;
	}

//	printf("String: %lf %s\n",double_time,string);

	char watts_string[BUFSIZ];
	double watts;
	int i=0,j=0,commas=0;
	while(i<strlen(string)) {
		if (string[i]==',') commas++;
		if (commas==3){
			i++;
			while(string[i]!=',') {
				watts_string[j]=string[i];
				i++;
				j++;
			}
			watts_string[j]=0;
			break;
		}
		i++;
	}

	watts=atof(watts_string);
	watts/=10.0;

	printf("%lf %.1lf ",double_time,watts);


	return 0;
}

#define MAX_CPUS	16

static int num_cpus=0;
static int cpu_freq_fds[MAX_CPUS];
static int cpu_freq_max[MAX_CPUS];
static int cpu_freq_current[MAX_CPUS];

static int open_cpus(void) {

	int i,result;
	int fd;
	char filename[BUFSIZ];
	char temp_value[BUFSIZ];

	for(i=0;i<MAX_CPUS;i++) {
		sprintf(filename,"/sys/devices/system/cpu/cpu%d/cpufreq/cpuinfo_max_freq",i);
		fd=open(filename,O_RDONLY);
		if (fd<0) {
			break;
		}
		result=read(fd,temp_value,BUFSIZ);
		if (result<0) {
			break;
		}
		temp_value[result]=0;
		sscanf(temp_value,"%d",&cpu_freq_max[i]);
		close(fd);
	}
	num_cpus=i;
	printf("Found %d cpus\n",num_cpus);
	for(i=0;i<num_cpus;i++) {
		printf("\t%d: %d\n",i,cpu_freq_max[i]);
	}

	for(i=0;i<num_cpus;i++) {
		sprintf(filename,"/sys/devices/system/cpu/cpu%d/cpufreq/cpuinfo_cur_freq",i);
		fd=open(filename,O_RDONLY);
		if (fd<0) {
			break;
		}
		cpu_freq_fds[i]=fd;
	}

	return num_cpus;
}


static int read_cpus(void) {

	int i,result;
	char temp_value[BUFSIZ];

	for(i=0;i<num_cpus;i++) {
		lseek(cpu_freq_fds[i],0,SEEK_SET);
		result=read(cpu_freq_fds[i],temp_value,BUFSIZ);
		temp_value[result]=0;
		sscanf(temp_value,"%d",&cpu_freq_current[i]);
	}

	return i;
}


static int open_temperature(void) {

	int fd;

	fd=open("/sys/class/thermal/thermal_zone0/temp",O_RDONLY);
	if (fd<0) {
		fprintf(stderr,"Error opening temperature file!\n");
		return -1;
	}

	return fd;
}

double read_temperature(int fd) {

	char buffer[256];
	double temp_temp;
	int result;

	result=lseek(fd,0,SEEK_SET);
	if (result<0) {
		fprintf(stderr,"Error with lseek!\n");
		return -1000;
	}

	result=read(fd,buffer,256);
	if (result<0) {
		fprintf(stderr,"Error reading temperature!\n");
		return -1000;
	}

	sscanf(buffer,"%lf",&temp_temp);

	return temp_temp/1000.0;
}

int main(int argc, char ** argv) {

	int ret,i;
	char device_name[BUFSIZ];
	int wu_fd = 0;
	int temp_fd = 0;
	struct sigaction sa;
	double temperature;

	/* Check command line */
	if (argc>1) {
		strncpy(device_name,argv[1],BUFSIZ-1);
	}
	else {
		strncpy(device_name,"ttyUSB0",BUFSIZ-1);
	}

	/* Print help? */
	/* Print version? */

	/*********************/
	/* setup cpus        */
	/*********************/

	open_cpus();

	/*********************/
	/* setup temperature */
	/*********************/
	temp_fd=open_temperature();
	if (temp_fd<0) {
		return -1;
	}

	/* setup control-c handler */
	memset(&sa, 0, sizeof(struct sigaction));
	sa.sa_sigaction = ctrlc_handler;
	sa.sa_flags = SA_SIGINFO;

	if (sigaction( SIGINT, &sa, NULL) < 0) {
		fprintf(stderr,"Error setting up signal handler\n");
		return -1;
	}

	/*************************/
	/* Open device           */
	/*************************/
	wu_fd = open_device(device_name);
	if (wu_fd<0) {
		return wu_fd;
	}

	if (debug) {
		fprintf(stderr,"DEBUG: %s is opened\n", device_name);
	}

	ret = setup_serial_device(wu_fd);
	if (ret) {
		close(wu_fd);
		return -1;
	}

	/* Enable logging */
	ret = wu_start_external_log(wu_fd,1);
	if (ret) {
		fprintf(stderr,"Error enabling logging\n");
		close(wu_fd);
		return 0;
	}

	/* Read data */
	while (1) {
		ret = wu_read(wu_fd);

		temperature=read_temperature(temp_fd);
		printf("%.2lf ",temperature);

		read_cpus();
		for(i=0;i<num_cpus;i++) {
			printf("%d ",cpu_freq_current[i]);
		}

		printf("\n");

		usleep(500000);

		if (done_running) break;
	}

	wu_stop_external_log(wu_fd);

	printf("(* %d missed samples *)\n",missed_samples);

	close(wu_fd);

	return 0;
}
