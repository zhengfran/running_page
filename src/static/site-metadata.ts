interface ISiteMetadataResult {
  siteTitle: string;
  siteUrl: string;
  description: string;
  logo: string;
  navLinks: {
    name: string;
    url: string;
  }[];
}

const data: ISiteMetadataResult = {
  siteTitle: 'Running Page',
  siteUrl: 'https://sunroof.zhengzhicheng.com/run',
  logo: 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQTtc69JxHNcmN1ETpMUX4dozAgAN6iPjWalQ&usqp=CAU',
  description: 'Zheng Zhicheng Running History',
  navLinks: [
    {
      name: 'Blog',
      url: 'https://sunroof.zhengzhicheng.com',
    },
    {
      name: 'About',
      url: 'https://github.com/zhengfran',
    },
  ],
};

export default data;
